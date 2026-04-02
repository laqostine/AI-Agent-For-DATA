"""FurniVision AI -- Pipeline start and status routes."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.state import StateManager
from pipeline.tasks import run_pipeline_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects/{project_id}/pipeline", tags=["pipeline"])

_state = StateManager()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class StartPipelineRequest(BaseModel):
    mode: str = "single_room"  # "single_room" | "all_rooms"
    target_room_id: str | None = None


class StartPipelineResponse(BaseModel):
    job_id: str
    project_id: str
    mode: str
    message: str


class PipelineStatusResponse(BaseModel):
    project_id: str
    job_id: str
    current_stage: int
    stage_name: str
    rooms: list[dict]
    gate_1_confirmed: bool
    gate_2_rooms_approved: dict
    started_at: str
    estimated_complete_at: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartPipelineResponse, status_code=202)
async def start_pipeline(project_id: str, body: StartPipelineRequest):
    """Start the pipeline as a background Celery task.

    Modes:
        - ``single_room``: requires ``target_room_id`` in the body.
        - ``all_rooms``: runs the full pipeline with human gates.
    """
    # Validate project
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if body.mode not in ("single_room", "all_rooms"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {body.mode}. Must be 'single_room' or 'all_rooms'.",
        )

    if body.mode == "single_room" and not body.target_room_id:
        raise HTTPException(
            status_code=400,
            detail="target_room_id is required when mode is 'single_room'",
        )

    # Validate that the target room exists (if specified)
    if body.target_room_id:
        room_ids = {r.id for r in project.rooms}
        if body.target_room_id not in room_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Room {body.target_room_id} not found in project {project_id}",
            )

    # Dispatch Celery task
    try:
        result = run_pipeline_task.delay(
            project_id=project_id,
            mode=body.mode,
            target_room_id=body.target_room_id,
        )
        job_id = result.id
    except Exception:
        logger.exception("Failed to enqueue pipeline task for project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to start pipeline task")

    logger.info(
        "Pipeline task enqueued: project=%s mode=%s job=%s",
        project_id,
        body.mode,
        job_id,
    )

    return StartPipelineResponse(
        job_id=job_id,
        project_id=project_id,
        mode=body.mode,
        message=f"Pipeline started in '{body.mode}' mode",
    )


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(project_id: str):
    """Return the full pipeline state from Firestore."""
    try:
        ps = await _state.get_pipeline_state(project_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"No pipeline state found for project {project_id}",
        )
    except Exception:
        logger.exception("Failed to load pipeline state for project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to load pipeline state")

    return PipelineStatusResponse(
        project_id=ps.project_id,
        job_id=ps.job_id,
        current_stage=ps.current_stage,
        stage_name=ps.stage_name,
        rooms=[r.model_dump() for r in ps.rooms],
        gate_1_confirmed=ps.gate_1_confirmed,
        gate_2_rooms_approved=ps.gate_2_rooms_approved,
        started_at=ps.started_at.isoformat(),
        estimated_complete_at=ps.estimated_complete_at.isoformat() if ps.estimated_complete_at else None,
        error=ps.error,
    )
