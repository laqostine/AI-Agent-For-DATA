"""FurniVision AI — Pipeline orchestrator: coordinates agents across stages."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from models.project import Project, ProjectBrief, RoomGeometry, FurnitureItem
from models.pipeline import PipelineState, RoomPipelineState, FrameStatus
from models.extraction import ExtractionResult
from pipeline.state import StateManager
from config import (
    HUMAN_GATE_TIMEOUT_HOURS,
    MAX_REGENERATION_ATTEMPTS,
    QC_CONSISTENCY_THRESHOLD,
    FRAMES_PER_ROOM,
)

logger = logging.getLogger(__name__)

# Gate polling interval in seconds
_GATE_POLL_INTERVAL = 10


class PipelineOrchestrator:
    """Runs the full FurniVision pipeline (agents 1-5) with human gates."""

    def __init__(self) -> None:
        self.state = StateManager()

    # ------------------------------------------------------------------
    # Lazy agent imports (avoids heavy imports at module level)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_parser_agent():
        from agents.agent1_parser import ParserAgent
        return ParserAgent()

    @staticmethod
    def _get_planner_agent():
        from agents.agent2_planner import PlannerAgent
        return PlannerAgent()

    @staticmethod
    def _get_composer_agent():
        from agents.agent2_5_composer import SceneComposerAgent
        return SceneComposerAgent()

    @staticmethod
    def _get_generator_agent():
        from agents.agent3_generator import GeneratorAgent
        return GeneratorAgent()

    @staticmethod
    def _get_validator_agent():
        from agents.agent4_validator import ValidatorAgent
        return ValidatorAgent()

    @staticmethod
    def _get_animator_agent():
        from agents.agent5_animator import AnimatorAgent
        return AnimatorAgent()

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def run_full_pipeline(self, project_id: str) -> None:
        """Execute the complete 5-stage pipeline with human gates."""
        job_id = str(uuid.uuid4())
        logger.info("Starting full pipeline for project %s (job=%s)", project_id, job_id)

        try:
            # --- STAGE 0: Load project ---
            project = await self.state.get_project(project_id)
            pipeline_state = PipelineState(
                project_id=project_id,
                job_id=job_id,
                current_stage=0,
                stage_name="loading",
                started_at=datetime.utcnow(),
                estimated_complete_at=datetime.utcnow() + timedelta(hours=2),
            )
            await self.state.create_pipeline_state(pipeline_state)
            await self.state.update_project(project_id, {"status": "analysing"})

            # --- STAGE 1: Agent 1 — Parse PDF + Furniture ---
            await self._update_state(project_id, 1, "parsing")
            parser = self._get_parser_agent()

            # Download files from storage to local temp dir for Agent 1
            from services.storage import StorageService
            from config import TEMP_DIR
            storage = StorageService()
            proj_tmp = TEMP_DIR / f"parse_{project_id}"
            proj_tmp.mkdir(parents=True, exist_ok=True)

            floorplan_local = str(proj_tmp / Path(project.floorplan_gcs_path).name)
            await storage.download_file(project.floorplan_gcs_path, floorplan_local)

            furniture_images = []
            for fi in project.furniture_gcs_paths:
                ext = Path(fi["gcs_path"]).suffix or ".png"
                local_path = str(proj_tmp / f"furniture_{fi['id']}{ext}")
                await storage.download_file(fi["gcs_path"], local_path)
                furniture_images.append({
                    "id": fi.get("id", ""),
                    "path": local_path,
                    "filename": fi.get("filename", ""),
                })

            extraction = await parser.parse(
                pdf_path=floorplan_local,
                furniture_images=furniture_images,
                brief_data={"project_id": project_id},
            )
            await self.state.save_extraction(project_id, extraction)
            await self.state.update_project(project_id, {"status": "awaiting_gate1"})
            await self._update_state(project_id, 1, "awaiting_gate1")

            # --- GATE 1: Wait for human confirmation ---
            logger.info("Pipeline %s waiting at Gate 1", project_id)
            gate1_ok = await self._wait_for_gate(
                project_id, gate=1, timeout_hours=HUMAN_GATE_TIMEOUT_HOURS
            )
            if not gate1_ok:
                await self._fail_pipeline(project_id, "Gate 1 timed out — no human confirmation received")
                return

            # Reload project (human may have updated brief / room selections)
            project = await self.state.get_project(project_id)
            extraction = await self.state.get_extraction(project_id)

            # Download reference renders for visual anchoring (if any)
            reference_images = await self._download_reference_images(project)

            # Convert floor plan PDF → PNG bytes for SceneComposer
            floor_plan_image_bytes = await self._load_floor_plan_image(project)

            # --- STAGE 2: For each room — Agents 2→2.5→3→4→5 ---
            await self.state.update_project(project_id, {"status": "generating"})
            await self._update_state(project_id, 2, "generating_rooms")

            # Build room pipeline state entries
            rooms_to_process = project.rooms
            room_states = [
                RoomPipelineState(
                    room_id=room.id,
                    label=room.label,
                    status="pending",
                    frames=[
                        FrameStatus(frame_idx=i, frame_type="keyframe" if i % 4 == 0 else "interpolation")
                        for i in range(FRAMES_PER_ROOM)
                    ],
                )
                for room in rooms_to_process
            ]
            await self.state.update_pipeline_state(
                project_id,
                {"rooms": [rs.model_dump() for rs in room_states]},
            )

            # Run all rooms
            for room in rooms_to_process:
                room_furniture = room.furniture_items
                await self._run_room_pipeline(
                    project_id, room.id, room, room_furniture, project.brief,
                    reference_images=reference_images,
                    floor_plan_image_bytes=floor_plan_image_bytes,
                )

            # --- Update state to awaiting_gate2 ---
            await self.state.update_project(project_id, {"status": "awaiting_gate2"})
            await self._update_state(project_id, 3, "awaiting_gate2")

            # --- GATE 2: Wait for per-room approval ---
            logger.info("Pipeline %s waiting at Gate 2", project_id)
            gate2_ok = await self._wait_for_gate(
                project_id, gate=2, timeout_hours=HUMAN_GATE_TIMEOUT_HOURS
            )
            if not gate2_ok:
                await self._fail_pipeline(project_id, "Gate 2 timed out — not all rooms approved")
                return

            # --- STAGE 3: Re-run rejected rooms ---
            ps = await self.state.get_pipeline_state(project_id)
            rejected_rooms = [
                r for r in ps.rooms if r.status == "rejected"
            ]
            if rejected_rooms:
                await self._update_state(project_id, 3, "regenerating_rejected")
                project = await self.state.get_project(project_id)
                for room_state in rejected_rooms:
                    room = next((r for r in project.rooms if r.id == room_state.room_id), None)
                    if room:
                        await self._run_room_pipeline(
                            project_id, room.id, room, room.furniture_items, project.brief
                        )

            # --- STAGE 4: Assemble outputs ---
            await self._update_state(project_id, 4, "assembling_outputs")
            # Output assembly is handled by individual room pipelines
            # (hero renders, video, HLS, viewer manifest are created by agents 4-5)

            # --- STAGE 5: Complete ---
            await self.state.update_project(project_id, {"status": "complete"})
            await self._update_state(project_id, 5, "complete")
            logger.info("Pipeline complete for project %s", project_id)

        except Exception:
            logger.exception("Pipeline failed for project %s", project_id)
            await self._fail_pipeline(project_id, "Unhandled pipeline error")
            raise

    # ------------------------------------------------------------------
    # Single room mode
    # ------------------------------------------------------------------

    async def run_single_room(self, project_id: str, room_id: str) -> None:
        """Run agents 2-5 for a single room (Phase 1 / demo mode)."""
        logger.info("Running single-room pipeline: project=%s room=%s", project_id, room_id)

        project = await self.state.get_project(project_id)
        room = next((r for r in project.rooms if r.id == room_id), None)
        if room is None:
            raise ValueError(f"Room {room_id} not found in project {project_id}")

        # Ensure pipeline state exists
        try:
            await self.state.get_pipeline_state(project_id)
        except ValueError:
            ps = PipelineState(
                project_id=project_id,
                job_id=str(uuid.uuid4()),
                current_stage=2,
                stage_name="single_room",
                rooms=[
                    RoomPipelineState(
                        room_id=room.id,
                        label=room.label,
                        status="pending",
                        frames=[
                            FrameStatus(
                                frame_idx=i,
                                frame_type="keyframe" if i % 4 == 0 else "interpolation",
                            )
                            for i in range(FRAMES_PER_ROOM)
                        ],
                    )
                ],
            )
            await self.state.create_pipeline_state(ps)

        reference_images = await self._download_reference_images(project)
        floor_plan_image_bytes = await self._load_floor_plan_image(project)
        await self.state.update_project(project_id, {"status": "generating"})
        await self._run_room_pipeline(
            project_id, room_id, room, room.furniture_items, project.brief,
            reference_images=reference_images,
            floor_plan_image_bytes=floor_plan_image_bytes,
        )
        await self.state.update_project(project_id, {"status": "awaiting_gate2"})

    # ------------------------------------------------------------------
    # Room pipeline (Agents 2→3→4→5)
    # ------------------------------------------------------------------

    async def _run_room_pipeline(
        self,
        project_id: str,
        room_id: str,
        room: RoomGeometry,
        furniture_items: list[FurnitureItem],
        brief: ProjectBrief,
        reference_images: list[bytes] | None = None,
        floor_plan_image_bytes: bytes | None = None,
    ) -> None:
        """Execute the Agent 2→2.5→3→4→5 chain for a single room.

        reference_images: uploaded reference renders (highest priority)
        floor_plan_image_bytes: PNG of the floor plan for SceneComposer
        """
        logger.info("Room pipeline starting: project=%s room=%s (%s)", project_id, room_id, room.label)

        try:
            # --- Agent 2: Scene Planner ---
            await self.state.update_room_state(project_id, room_id, {"status": "planning"})
            planner = self._get_planner_agent()
            scene_plan = await planner.plan(
                room=room,
                furniture_items=furniture_items,
                brief=brief,
                project_style=getattr(brief, "overall_style", "modern"),
                project_id=project_id,
            )
            logger.info("Agent 2 complete for room %s: %d camera positions", room_id, len(scene_plan.camera_positions))

            # --- Agent 2.5: Scene Composer (floor plan + furniture → synthetic render) ---
            composed_reference: bytes | None = None
            if floor_plan_image_bytes:
                composer = self._get_composer_agent()
                # Collect furniture images for this room
                room_furniture_images = await self._download_room_furniture_images(
                    furniture_items=furniture_items,
                )
                if room_furniture_images:
                    try:
                        composed = await composer.compose(
                            room_id=room_id,
                            room_label=room.label,
                            floor_plan_bytes=floor_plan_image_bytes,
                            furniture_images=room_furniture_images,
                            scene_plan=scene_plan,
                        )
                        composed_reference = composed.reference_render
                        logger.info(
                            "Agent 2.5 composed render for room %s: %d bytes",
                            room_id, len(composed_reference),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Agent 2.5 SceneComposer failed for room %s: %s — using uploaded reference",
                            room_id, exc,
                        )

            # Priority: uploaded reference render > composed render
            effective_references = reference_images or (
                [composed_reference] if composed_reference else None
            )

            # --- Agent 3: Image Generator ---
            await self.state.update_room_state(project_id, room_id, {"status": "generating"})
            generator = self._get_generator_agent()
            # Retrieve job_id from pipeline state for frame tracking
            try:
                ps = await self.state.get_pipeline_state(project_id)
                job_id = ps.job_id
            except Exception:
                job_id = str(uuid.uuid4())
            generation_result = await generator.generate_all_frames(
                scene_plan=scene_plan,
                project_id=project_id,
                room_id=room_id,
                job_id=job_id,
                reference_images=effective_references,
            )
            logger.info("Agent 3 complete for room %s: %d frames generated", room_id, len(generation_result))

            # --- Agent 4: QC Validator ---
            await self.state.update_room_state(project_id, room_id, {"status": "validating"})
            validator = self._get_validator_agent()
            validation = await validator.validate(
                frames=generation_result,
                scene_plan=scene_plan,
                room_id=room_id,
            )
            qc_score = getattr(validation, "overall_score", getattr(validation, "consistency_score", 1.0))
            logger.info(
                "Agent 4 complete for room %s: score=%.2f",
                room_id, qc_score,
            )

            # Store QC score and hero frame URLs
            await self.state.update_room_state(project_id, room_id, {
                "qc_score": qc_score,
                "hero_frame_urls": getattr(validation, "graded_frame_urls", []),
            })

            if qc_score < QC_CONSISTENCY_THRESHOLD:
                logger.warning("Room %s low QC score (%.2f)", room_id, qc_score)

            # --- Agent 5: Animator ---
            await self.state.update_room_state(project_id, room_id, {"status": "animating"})
            animator = self._get_animator_agent()
            animation = await animator.animate(
                validated_frames=generation_result,
                scene_plan=scene_plan,
                project_id=project_id,
                room_id=room_id,
                reference_images=reference_images,
            )
            logger.info("Agent 5 complete for room %s: video=%s", room_id, animation.video_url)

            # Mark room complete
            await self.state.update_room_state(project_id, room_id, {
                "status": "complete",
                "video_url": animation.video_url,
                "preview_url": animation.preview_url if hasattr(animation, "preview_url") else None,
            })

        except Exception:
            logger.exception("Room pipeline failed: project=%s room=%s", project_id, room_id)
            await self.state.update_room_state(project_id, room_id, {
                "status": "failed",
            })
            raise

    # ------------------------------------------------------------------
    # Gate waiting
    # ------------------------------------------------------------------

    async def _wait_for_gate(
        self, project_id: str, gate: int, timeout_hours: int = 48
    ) -> bool:
        """Poll Firestore until the gate is confirmed or timeout expires.

        Returns True if gate was confirmed, False on timeout.
        """
        deadline = datetime.utcnow() + timedelta(hours=timeout_hours)
        while datetime.utcnow() < deadline:
            try:
                confirmed = await self.state.is_gate_confirmed(project_id, gate)
                if confirmed:
                    logger.info("Gate %d confirmed for project %s", gate, project_id)
                    return True
            except Exception:
                logger.exception("Error checking gate %d for project %s", gate, project_id)
            await asyncio.sleep(_GATE_POLL_INTERVAL)

        logger.warning("Gate %d timed out for project %s after %d hours", gate, project_id, timeout_hours)
        return False

    # ------------------------------------------------------------------
    # Reference image helpers
    # ------------------------------------------------------------------

    async def _load_floor_plan_image(self, project) -> bytes | None:
        """Convert the project's floor plan PDF to PNG bytes for SceneComposer.

        Returns the first page as PNG bytes, or None if unavailable.
        """
        gcs_path = getattr(project, "floorplan_gcs_path", "")
        if not gcs_path:
            return None
        try:
            from services.storage import StorageService
            from services.pdf_processor import PDFProcessor
            import tempfile, os
            storage = StorageService()
            # Download PDF to a temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            await storage.download_file(gcs_path, tmp_path)
            processor = PDFProcessor()
            pages = processor.convert_to_images(tmp_path, dpi=150)
            os.unlink(tmp_path)
            if pages:
                logger.info(
                    "Floor plan converted to PNG: %d bytes (page 1 of %d)",
                    len(pages[0]), len(pages),
                )
                return pages[0]
        except Exception as exc:
            logger.warning("Could not load floor plan image: %s", exc)
        return None

    async def _download_room_furniture_images(
        self,
        furniture_items,
    ) -> list[bytes]:
        """Download furniture catalogue images for a room from storage.

        Returns a list of raw image bytes (may be empty).
        """
        from services.storage import StorageService
        storage = StorageService()
        images: list[bytes] = []
        for item in furniture_items:
            gcs_url = getattr(item, "gcs_image_url", "")
            if not gcs_url:
                continue
            try:
                data = await storage.download_bytes(gcs_url)
                images.append(data)
            except Exception as exc:
                logger.warning(
                    "Could not download furniture image for %s: %s",
                    getattr(item, "item_name", item.id), exc,
                )
        return images

    async def _download_reference_images(self, project) -> list[bytes]:
        """Download all reference render images for this project.

        Returns a list of raw image bytes (may be empty if none uploaded).
        """
        refs = getattr(project, "reference_render_gcs_paths", []) or []
        if not refs:
            return []

        from services.storage import StorageService
        storage = StorageService()
        images: list[bytes] = []
        for ref in refs:
            gcs_path = ref.get("gcs_path", "")
            if not gcs_path:
                continue
            try:
                data = await storage.download_bytes(gcs_path)
                images.append(data)
                logger.info(
                    "Loaded reference render: %s (%d bytes)",
                    ref.get("filename", gcs_path), len(data),
                )
            except Exception as exc:
                logger.warning("Could not load reference render %s: %s", gcs_path, exc)
        return images

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    async def _update_state(self, project_id: str, stage: int, stage_name: str) -> None:
        """Convenience to update the pipeline stage and name."""
        await self.state.update_pipeline_state(project_id, {
            "current_stage": stage,
            "stage_name": stage_name,
        })
        logger.info("Pipeline %s → stage %d (%s)", project_id, stage, stage_name)

    async def _fail_pipeline(self, project_id: str, error_message: str) -> None:
        """Mark the pipeline and project as failed."""
        await self.state.update_project(project_id, {"status": "failed"})
        await self.state.update_pipeline_state(project_id, {
            "stage_name": "failed",
            "error": error_message,
        })
        logger.error("Pipeline failed for project %s: %s", project_id, error_message)
