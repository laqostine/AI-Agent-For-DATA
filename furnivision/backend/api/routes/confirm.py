"""FurniVision AI -- Extraction confirmation and room approval routes."""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.project import ProjectBrief, RoomGeometry, FurnitureItem
from models.extraction import FurnitureAssignment
from pipeline.state import StateManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["confirm"])

_state = StateManager()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class OverridesPayload(BaseModel):
    ceiling_height_m: float | None = None
    floor_material: str | None = None
    wall_color: str | None = None
    overall_dimensions_m: dict | None = None  # {w, d}


class ConfirmExtractionRequest(BaseModel):
    rooms: list[dict]  # user-edited room list
    furniture_assignments: list[dict]  # user-edited assignments
    overrides: OverridesPayload | None = None
    selected_rooms: list[str] | None = None  # subset of room ids to process
    mode: str = "single_room"  # "single_room" | "all_rooms"


class ConfirmExtractionResponse(BaseModel):
    project_id: str
    message: str
    job_id: str | None = None
    rooms_count: int
    furniture_count: int


class RoomApprovalRequest(BaseModel):
    approved: bool


class RoomRejectionRequest(BaseModel):
    approved: bool = False
    feedback: str


class RoomApprovalResponse(BaseModel):
    project_id: str
    room_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/extraction")
async def get_extraction(project_id: str):
    """Return Agent 1's extraction result for human review."""
    try:
        extraction = await _state.get_extraction(project_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"No extraction found for project {project_id}. "
            "Run the pipeline first.",
        )
    except Exception:
        logger.exception("Failed to load extraction for project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to load extraction")

    return extraction.model_dump()


@router.post("/confirm/extraction", response_model=ConfirmExtractionResponse)
async def confirm_extraction(project_id: str, body: ConfirmExtractionRequest):
    """Human confirms (and optionally corrects) the Agent 1 extraction.

    This sets gate_1_confirmed = True, updates the project brief and room
    data, then triggers agents 2-5 for the selected rooms.
    """
    # Validate project
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Build updated brief from overrides
    brief_updates: dict = {}
    if body.overrides:
        if body.overrides.ceiling_height_m is not None:
            brief_updates["ceiling_height_m"] = body.overrides.ceiling_height_m
        if body.overrides.floor_material is not None:
            brief_updates["floor_material"] = body.overrides.floor_material
        if body.overrides.wall_color is not None:
            brief_updates["wall_color"] = body.overrides.wall_color
        if body.overrides.overall_dimensions_m is not None:
            brief_updates["overall_dimensions_m"] = body.overrides.overall_dimensions_m

    # Merge existing brief with overrides
    current_brief = project.brief.model_dump()
    current_brief.update(brief_updates)

    # Build room objects from user-confirmed data
    confirmed_rooms: list[dict] = []
    for room_data in body.rooms:
        # Ensure each room has an id
        if "id" not in room_data:
            room_data["id"] = str(uuid.uuid4())

        # Attach furniture items based on assignments
        room_furniture = []
        for assignment in body.furniture_assignments:
            if assignment.get("room_id") == room_data["id"]:
                room_furniture.append({
                    "id": str(uuid.uuid4()),
                    "furniture_image_index": assignment.get("furniture_image_index", 0),
                    "item_name": assignment.get("item_name", "Unknown"),
                    "item_type": assignment.get("item_type", ""),
                    "room_id": room_data["id"],
                })

        room_data["furniture_items"] = room_furniture
        confirmed_rooms.append(room_data)

    # Filter to selected rooms if specified
    if body.selected_rooms:
        confirmed_rooms = [
            r for r in confirmed_rooms if r.get("id") in body.selected_rooms
        ]

    if not confirmed_rooms:
        raise HTTPException(
            status_code=400,
            detail="No rooms to process after applying selection filter",
        )

    # Persist updates to project
    try:
        await _state.update_project(project_id, {
            "rooms": confirmed_rooms,
            "brief": current_brief,
            "status": "planning",
        })
    except Exception:
        logger.exception("Failed to update project %s with confirmed data", project_id)
        raise HTTPException(status_code=500, detail="Failed to update project")

    # Set gate 1 confirmed
    try:
        await _state.set_gate_confirmed(project_id, gate=1, confirmed=True)
    except Exception:
        logger.exception("Failed to set gate 1 for project %s", project_id)
        # Non-fatal -- the pipeline poll will still detect it

    # Determine target room for single_room mode
    target_room_id = None
    if body.mode == "single_room" and confirmed_rooms:
        target_room_id = confirmed_rooms[0].get("id")

    # Trigger downstream pipeline (agents 2-5)
    job_id: str | None = None
    from config import GOOGLE_CLOUD_PROJECT
    if GOOGLE_CLOUD_PROJECT:
        # Production: Celery
        try:
            from pipeline.tasks import run_pipeline_task
            result = run_pipeline_task.delay(
                project_id=project_id,
                mode=body.mode,
                target_room_id=target_room_id,
            )
            job_id = result.id
        except Exception:
            logger.exception("Failed to enqueue pipeline task after confirmation")
    else:
        # Local: the pipeline started at upload is already waiting at Gate 1.
        # gate_1_confirmed was set above — it will wake up automatically.
        try:
            ps = await _state.get_pipeline_state(project_id)
            job_id = ps.job_id
        except Exception:
            job_id = str(uuid.uuid4())

    logger.info(
        "Extraction confirmed for project %s: %d rooms, %d assignments, mode=%s",
        project_id,
        len(confirmed_rooms),
        len(body.furniture_assignments),
        body.mode,
    )

    return ConfirmExtractionResponse(
        project_id=project_id,
        message="Extraction confirmed. Pipeline triggered for downstream processing.",
        job_id=job_id,
        rooms_count=len(confirmed_rooms),
        furniture_count=len(body.furniture_assignments),
    )


@router.post("/rooms/{room_id}/approve", response_model=RoomApprovalResponse)
async def approve_room(project_id: str, room_id: str, body: RoomApprovalRequest):
    """Mark a room's output as approved (Gate 2)."""
    # Validate project
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Validate room exists
    room_ids = {r.id for r in project.rooms}
    if room_id not in room_ids:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    if not body.approved:
        raise HTTPException(
            status_code=400,
            detail="Use the /reject endpoint to reject a room",
        )

    # Update pipeline state
    try:
        ps = await _state.get_pipeline_state(project_id)
        gate_2 = dict(ps.gate_2_rooms_approved)
        gate_2[room_id] = True
        await _state.update_pipeline_state(project_id, {
            "gate_2_rooms_approved": gate_2,
        })
        await _state.update_room_state(project_id, room_id, {"status": "complete"})
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="No pipeline state found. Start the pipeline first.",
        )
    except Exception:
        logger.exception("Failed to approve room %s", room_id)
        raise HTTPException(status_code=500, detail="Failed to update room approval")

    logger.info("Room %s approved for project %s", room_id, project_id)

    return RoomApprovalResponse(
        project_id=project_id,
        room_id=room_id,
        status="approved",
        message=f"Room '{room_id}' approved",
    )


@router.post("/rooms/{room_id}/reject", response_model=RoomApprovalResponse)
async def reject_room(project_id: str, room_id: str, body: RoomRejectionRequest):
    """Reject a room's output and trigger regeneration with feedback."""
    # Validate project
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Validate room exists
    room_ids = {r.id for r in project.rooms}
    if room_id not in room_ids:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    if not body.feedback or not body.feedback.strip():
        raise HTTPException(
            status_code=400,
            detail="Feedback is required when rejecting a room",
        )

    # Update pipeline state
    try:
        ps = await _state.get_pipeline_state(project_id)
        gate_2 = dict(ps.gate_2_rooms_approved)
        gate_2[room_id] = False
        await _state.update_pipeline_state(project_id, {
            "gate_2_rooms_approved": gate_2,
        })
        await _state.update_room_state(project_id, room_id, {
            "status": "rejected",
            "rejection_feedback": body.feedback.strip(),
        })
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="No pipeline state found. Start the pipeline first.",
        )
    except Exception:
        logger.exception("Failed to reject room %s", room_id)
        raise HTTPException(status_code=500, detail="Failed to update room rejection")

    # Trigger regeneration task
    try:
        from pipeline.tasks import regenerate_room_task
        regenerate_room_task.delay(
            project_id=project_id,
            room_id=room_id,
            feedback=body.feedback.strip(),
        )
    except Exception:
        logger.exception("Failed to enqueue regeneration task for room %s", room_id)
        # Non-fatal -- user can retry

    logger.info(
        "Room %s rejected for project %s with feedback: %s",
        room_id,
        project_id,
        body.feedback[:120],
    )

    return RoomApprovalResponse(
        project_id=project_id,
        room_id=room_id,
        status="rejected",
        message=f"Room '{room_id}' rejected. Regeneration triggered with feedback.",
    )
