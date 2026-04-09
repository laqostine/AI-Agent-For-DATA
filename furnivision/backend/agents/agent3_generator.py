"""FurniVision AI — Agent 3: Generator — 2 Imagen keyframes per room.

If reference renders are supplied, Gemini analyses them first to create
a visually-grounded prompt that matches the actual room design (dimensions,
furniture, materials, lighting). Without references, falls back to the
scene plan prompts from Agent 2.
"""

import asyncio
import logging
from datetime import datetime

from models.pipeline import FrameStatus
from services.imagen import ImagenService, ImagenError
from services.storage import StorageService
from config import GCS_PATH_FRAMES_RAW, MAX_REGENERATION_ATTEMPTS

logger = logging.getLogger(__name__)

NUM_KEYFRAMES = 2


class GeneratorAgent:
    """Agent 3 — generates 2 Imagen 4 keyframes for a room."""

    def __init__(self) -> None:
        self.imagen = ImagenService()
        self.storage = StorageService()

    async def generate_all_frames(
        self,
        scene_plan,  # agents.agent2_planner.ScenePlan
        project_id: str,
        room_id: str,
        job_id: str,
        reference_images: list[bytes] | None = None,
    ) -> list[FrameStatus]:
        """Generate 2 keyframes.

        If reference_images provided, Gemini analyses them to build
        a prompt that faithfully reproduces the room's design intent.
        Otherwise falls back to the scene plan prompts.
        """
        logger.info(
            "GeneratorAgent.generate_all_frames — project=%s, room=%s, refs=%d",
            project_id, room_id, len(reference_images) if reference_images else 0,
        )

        if reference_images:
            prompts = await self._build_reference_grounded_prompts(
                scene_plan=scene_plan,
                reference_images=reference_images,
            )
        else:
            # Fallback: use planner prompts (wide + midpoint shots)
            planner_prompts = scene_plan.prompts
            wide_idx = 0
            detail_idx = min(len(planner_prompts) // 2, len(planner_prompts) - 1)
            prompts = [planner_prompts[wide_idx], planner_prompts[detail_idx]]

        frame_statuses: list[FrameStatus] = [
            FrameStatus(frame_idx=i, frame_type="keyframe", status="pending")
            for i in range(NUM_KEYFRAMES)
        ]

        # Always pass reference to each frame generation when available
        ref_img = reference_images[0] if reference_images else None

        tasks = [
            self._generate_single_frame(
                frame_idx=i,
                prompt=prompts[min(i, len(prompts) - 1)],
                frame_status=frame_statuses[i],
                project_id=project_id,
                room_id=room_id,
                reference_image=ref_img,
            )
            for i in range(NUM_KEYFRAMES)
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        complete_count = sum(1 for fs in frame_statuses if fs.status == "complete")
        logger.info("Generation complete — %d/%d keyframes succeeded", complete_count, NUM_KEYFRAMES)
        return frame_statuses

    async def _build_reference_grounded_prompts(
        self,
        scene_plan,
        reference_images: list[bytes],
    ) -> list[str]:
        """Use Gemini to analyse the reference renders and build precise Imagen prompts.

        Returns 2 prompts:
          [0] Wide overview matching the reference composition
          [1] Detail/focal shot matching the reference furniture
        """
        from services.gemini import GeminiService
        gemini = GeminiService()

        room_label = getattr(scene_plan.room, "label", "room")
        style_anchor = getattr(scene_plan, "style_anchor", "")

        # Build furniture description from layout
        layout = getattr(scene_plan, "furniture_layout", [])
        furniture_names = [
            item.get("item_name") or item.get("item_id", "")
            for item in layout[:8]
        ]
        furniture_names = [n for n in furniture_names if n]
        furniture_str = f"Furniture: {', '.join(furniture_names)}. " if furniture_names else ""

        system_prompt = (
            "You are a photorealistic interior visualization prompt engineer. "
            "Analyse the provided reference render(s) of an interior space and describe "
            "exactly what you see: room shape and proportions, floor material and color, "
            "wall color and finish, ceiling height and lighting fixtures, every piece of "
            "furniture (type, color, material, exact placement), decorative items, "
            "window/door positions, and overall mood. Be extremely specific and precise."
        )

        user_prompt = (
            f"This is a '{room_label}' space.\n"
            f"{furniture_str}"
            f"Style context: {style_anchor[:300]}\n\n"
            "Generate TWO Imagen 4 prompts for this room:\n"
            "1. A wide overview shot (same perspective as reference, full room visible)\n"
            "2. A focused detail shot (key furniture arrangement, close-up composition)\n\n"
            "Each prompt must be photorealistic, architecturally precise, and reproduce "
            "EXACTLY the same room layout, furniture, colors, and materials as the reference. "
            "Include: room dimensions feel, all visible furniture with colors/materials, "
            "floor/wall/ceiling materials, lighting style, no people.\n\n"
            'Respond ONLY with JSON: {"wide_prompt": "...", "detail_prompt": "..."}'
        )

        try:
            result = await gemini.analyze_images_structured(
                images=reference_images[:2],  # max 2 reference images
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            wide_prompt = result.get("wide_prompt", "")
            detail_prompt = result.get("detail_prompt", "")
            if wide_prompt and detail_prompt:
                logger.info(
                    "Reference-grounded prompts generated (wide=%.80s...)", wide_prompt
                )
                return [wide_prompt, detail_prompt]
        except Exception as exc:
            logger.warning("Failed to build reference-grounded prompts: %s", exc)

        # Fallback to planner prompts
        planner_prompts = scene_plan.prompts
        return [
            planner_prompts[0],
            planner_prompts[min(len(planner_prompts) // 2, len(planner_prompts) - 1)],
        ]

    async def _generate_single_frame(
        self,
        frame_idx: int,
        prompt: str,
        frame_status: FrameStatus,
        project_id: str,
        room_id: str,
        reference_image: bytes | None = None,
    ) -> None:
        """Generate a single frame with retries and upload to storage.

        If reference_image is provided, uses Gemini Flash Image (image-to-image)
        which maintains visual consistency with the reference render.
        Otherwise falls back to Imagen 4 text-to-image.
        """
        frame_status.status = "generating"
        gcs_path = GCS_PATH_FRAMES_RAW.format(
            project_id=project_id, room_id=room_id, n=frame_idx
        )

        mode = "gemini-img2img" if reference_image else "imagen4-txt2img"
        logger.info("Generating keyframe %d [%s] (prompt=%.100s...)", frame_idx, mode, prompt)

        last_error: Exception | None = None
        for attempt in range(1, MAX_REGENERATION_ATTEMPTS + 1):
            try:
                frame_status.attempts = attempt
                image_bytes = await self.imagen.generate_frame_with_retry(
                    prompt=prompt,
                    reference_image=reference_image,
                    reference_mime="image/jpeg",
                    max_retries=1,  # outer loop handles retries
                )

                await self.storage.upload_bytes(
                    data=image_bytes,
                    gcs_path=gcs_path,
                    content_type="image/png",
                )

                frame_status.status = "complete"
                frame_status.gcs_url = gcs_path
                frame_status.completed_at = datetime.utcnow()

                logger.info(
                    "Keyframe %d generated successfully (attempt %d) -> %s",
                    frame_idx, attempt, gcs_path,
                )
                return

            except Exception as exc:
                last_error = exc
                wait = 2.0 ** attempt
                logger.warning(
                    "Keyframe %d attempt %d/%d failed: %s. Retrying in %.1fs...",
                    frame_idx, attempt, MAX_REGENERATION_ATTEMPTS, exc, wait,
                )
                await asyncio.sleep(wait)

        frame_status.status = "failed"
        frame_status.error_message = str(last_error)
        logger.error("Keyframe %d failed after %d attempts", frame_idx, MAX_REGENERATION_ATTEMPTS)
