"""FurniVision AI — Local mock pipeline (no AI calls required).

Generates realistic fake extraction + room renders for local development.
Activated automatically when GOOGLE_CLOUD_PROJECT is not set.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from config import TEMP_DIR, FRAMES_PER_ROOM
from models.extraction import (
    ExtractionResult,
    RoomGeometryExtracted,
    FurnitureItemExtracted,
    FurnitureAssignment,
    ScaleInfo,
    MissingField,
)
from models.pipeline import PipelineState, RoomPipelineState, FrameStatus
from models.project import RoomGeometry, FurnitureItem, ProjectBrief
from pipeline.state import StateManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_ROOMS = [
    {
        "id": "room_01",
        "label": "Living Room",
        "area_sqm_estimated": 28.5,
        "polygon_relative": [[0.0, 0.0], [0.55, 0.0], [0.55, 0.6], [0.0, 0.6]],
    },
    {
        "id": "room_02",
        "label": "Master Bedroom",
        "area_sqm_estimated": 18.0,
        "polygon_relative": [[0.55, 0.0], [1.0, 0.0], [1.0, 0.5], [0.55, 0.5]],
    },
    {
        "id": "room_03",
        "label": "Kitchen",
        "area_sqm_estimated": 12.0,
        "polygon_relative": [[0.0, 0.6], [0.45, 0.6], [0.45, 1.0], [0.0, 1.0]],
    },
]

_MOCK_FURNITURE_ITEMS = [
    {"furniture_image_index": 0, "item_name": "Sofa", "item_type": "sofa", "color_primary": "grey"},
    {"furniture_image_index": 1, "item_name": "Coffee Table", "item_type": "table", "color_primary": "oak"},
    {"furniture_image_index": 2, "item_name": "King Bed", "item_type": "bed", "color_primary": "white"},
]

_MOCK_ASSIGNMENTS = [
    {"furniture_image_index": 0, "room_id": "room_01", "item_name": "Sofa", "confidence": 0.95},
    {"furniture_image_index": 1, "room_id": "room_01", "item_name": "Coffee Table", "confidence": 0.88},
    {"furniture_image_index": 2, "room_id": "room_02", "item_name": "King Bed", "confidence": 0.97},
]

# A small 1×1 white PNG encoded as bytes (placeholder render)
import base64
_WHITE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)
_PLACEHOLDER_PNG = base64.b64decode(_WHITE_PNG_B64)


# ---------------------------------------------------------------------------
# Main mock pipeline
# ---------------------------------------------------------------------------

async def run_local_pipeline(project_id: str, mode: str, target_room_id: str | None) -> None:
    """Run a fully local mock pipeline — no AI calls, instant results."""
    state = StateManager()
    job_id = str(uuid.uuid4())
    logger.info("LOCAL mock pipeline starting: project=%s mode=%s", project_id, mode)

    try:
        project = await state.get_project(project_id)

        # --- Create pipeline state ---
        ps = PipelineState(
            project_id=project_id,
            job_id=job_id,
            current_stage=0,
            stage_name="loading",
            started_at=datetime.utcnow(),
            estimated_complete_at=datetime.utcnow() + timedelta(seconds=30),
        )
        await state.create_pipeline_state(ps)
        await state.update_project(project_id, {"status": "analysing"})

        # --- Stage 1: Mock extraction ---
        await state.update_pipeline_state(project_id, {"current_stage": 1, "stage_name": "parsing"})
        await asyncio.sleep(0.5)  # simulate brief work

        num_furniture = len(project.furniture_gcs_paths)
        rooms_extracted = [RoomGeometryExtracted(**r) for r in _MOCK_ROOMS]
        furniture_items = [
            FurnitureItemExtracted(**_MOCK_FURNITURE_ITEMS[i % len(_MOCK_FURNITURE_ITEMS)])
            for i in range(max(num_furniture, 1))
        ]
        assignments = [
            FurnitureAssignment(**_MOCK_ASSIGNMENTS[i % len(_MOCK_ASSIGNMENTS)])
            for i in range(max(num_furniture, 1))
        ]

        extraction = ExtractionResult(
            project_id=project_id,
            rooms=rooms_extracted,
            furniture_items=furniture_items,
            furniture_assignments=assignments,
            scale_info=ScaleInfo(
                has_scale_bar=True,
                calibration_possible=True,
                notes="Mock scale — 1px = 0.01m",
            ),
            missing_fields=[
                MissingField(
                    field="ceiling_height_m",
                    question="What is the ceiling height?",
                    default_guess=2.7,
                    importance="high",
                )
            ],
            overall_style="Modern Contemporary",
            lighting_cues="Large south-facing windows, natural light dominant",
            confidence_overall=0.92,
        )
        await state.save_extraction(project_id, extraction)
        await state.update_project(project_id, {"status": "awaiting_gate1"})
        await state.update_pipeline_state(project_id, {"current_stage": 1, "stage_name": "awaiting_gate1"})

        logger.info("LOCAL mock extraction saved for project %s", project_id)

        # --- Gate 1: wait for human confirmation ---
        deadline = datetime.utcnow() + timedelta(hours=48)
        while datetime.utcnow() < deadline:
            confirmed = await state.is_gate_confirmed(project_id, 1)
            if confirmed:
                break
            await asyncio.sleep(3)
        else:
            await state.update_pipeline_state(project_id, {"stage_name": "failed", "error": "Gate 1 timed out"})
            return

        project = await state.get_project(project_id)

        # --- Stage 2-5: Mock room rendering ---
        rooms_to_process = [
            r for r in project.rooms
            if (target_room_id is None or r.id == target_room_id)
        ]

        room_states = [
            RoomPipelineState(
                room_id=r.id,
                label=r.label,
                status="pending",
                frames=[
                    FrameStatus(
                        frame_idx=i,
                        frame_type="keyframe" if i % 4 == 0 else "interpolation",
                    )
                    for i in range(FRAMES_PER_ROOM)
                ],
            )
            for r in rooms_to_process
        ]
        await state.update_pipeline_state(
            project_id,
            {"rooms": [rs.model_dump() for rs in room_states], "current_stage": 2, "stage_name": "generating_rooms"},
        )
        await state.update_project(project_id, {"status": "generating"})

        for room in rooms_to_process:
            await _mock_room_pipeline(state, project_id, room.id)

        await state.update_project(project_id, {"status": "awaiting_gate2"})
        await state.update_pipeline_state(project_id, {"current_stage": 3, "stage_name": "awaiting_gate2"})
        logger.info("LOCAL mock pipeline reached Gate 2: project=%s", project_id)

    except Exception:
        logger.exception("LOCAL mock pipeline failed: project=%s", project_id)
        try:
            await state.update_pipeline_state(project_id, {"stage_name": "failed", "error": "Mock pipeline error"})
            await state.update_project(project_id, {"status": "failed"})
        except Exception:
            pass
        raise


async def _mock_room_pipeline(state: StateManager, project_id: str, room_id: str) -> None:
    """Simulate agents 2-5 for one room with placeholder outputs."""
    logger.info("LOCAL mock room pipeline: project=%s room=%s", project_id, room_id)

    # Planning
    await state.update_room_state(project_id, room_id, {"status": "planning"})
    await asyncio.sleep(0.3)

    # Generating — save placeholder frame files
    await state.update_room_state(project_id, room_id, {"status": "generating"})
    frame_dir = TEMP_DIR / "storage" / "projects" / project_id / "rooms" / room_id / "frames" / "raw"
    frame_dir.mkdir(parents=True, exist_ok=True)

    frame_updates = []
    for i in range(FRAMES_PER_ROOM):
        frame_path = frame_dir / f"frame_{i:03d}.png"
        frame_path.write_bytes(_PLACEHOLDER_PNG)
        frame_updates.append({
            "frame_idx": i,
            "frame_type": "keyframe" if i % 4 == 0 else "interpolation",
            "status": "complete",
            "gcs_url": f"/api/v1/local-storage/projects/{project_id}/rooms/{room_id}/frames/raw/frame_{i:03d}.png",
        })
        if i % 8 == 0:
            await asyncio.sleep(0.05)

    preview_url = frame_updates[0]["gcs_url"]
    hero_urls = [f["gcs_url"] for f in frame_updates if f["frame_type"] == "keyframe"][:4]

    # Validating
    await state.update_room_state(project_id, room_id, {
        "status": "validating",
        "frames": frame_updates,
        "preview_url": preview_url,
    })
    await asyncio.sleep(0.2)

    # Animating — save placeholder video file
    video_dir = TEMP_DIR / "storage" / "projects" / project_id / "rooms" / room_id / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / "room.mp4"
    video_path.write_bytes(b"")  # empty placeholder

    video_url = f"/api/v1/local-storage/projects/{project_id}/rooms/{room_id}/video/room.mp4"

    await state.update_room_state(project_id, room_id, {"status": "animating"})
    await asyncio.sleep(0.2)

    # Complete
    await state.update_room_state(project_id, room_id, {
        "status": "complete",
        "frames": frame_updates,
        "preview_url": preview_url,
        "hero_frame_urls": hero_urls,
        "video_url": video_url,
        "qc_score": 0.94,
    })
    logger.info("LOCAL mock room complete: project=%s room=%s", project_id, room_id)
