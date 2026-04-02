"""FurniVision AI -- Celery task definitions for background pipeline execution."""

import asyncio
import logging

from celery import Celery

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

logger = logging.getLogger(__name__)

app = Celery(
    "furnivision",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def _run_async(coro):
    """Run an async coroutine in a new event loop (Celery workers are sync)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="run_pipeline", bind=True, max_retries=1)
def run_pipeline_task(
    self,
    project_id: str,
    mode: str = "single_room",
    target_room_id: str | None = None,
):
    """Start the pipeline for a project.

    Modes:
        - ``single_room``: run agents 2-5 for *target_room_id* only.
        - ``all_rooms``: run the full 5-stage pipeline with human gates.
    """
    from pipeline.orchestrator import PipelineOrchestrator

    logger.info(
        "Celery task run_pipeline: project=%s mode=%s room=%s",
        project_id,
        mode,
        target_room_id,
    )

    orchestrator = PipelineOrchestrator()
    try:
        if mode == "all_rooms":
            _run_async(orchestrator.run_full_pipeline(project_id))
        elif mode == "single_room":
            if not target_room_id:
                raise ValueError("target_room_id is required for single_room mode")
            _run_async(orchestrator.run_single_room(project_id, target_room_id))
        else:
            raise ValueError(f"Unknown pipeline mode: {mode}")
    except Exception as exc:
        logger.exception("Pipeline task failed: project=%s", project_id)
        raise self.retry(exc=exc, countdown=30) if self.request.retries < self.max_retries else exc


@app.task(name="run_room", bind=True, max_retries=1)
def run_room_task(self, project_id: str, room_id: str):
    """Run the single-room pipeline (agents 2-5) as a standalone Celery task."""
    from pipeline.orchestrator import PipelineOrchestrator

    logger.info("Celery task run_room: project=%s room=%s", project_id, room_id)

    orchestrator = PipelineOrchestrator()
    try:
        _run_async(orchestrator.run_single_room(project_id, room_id))
    except Exception as exc:
        logger.exception("Room task failed: project=%s room=%s", project_id, room_id)
        raise self.retry(exc=exc, countdown=30) if self.request.retries < self.max_retries else exc


@app.task(name="regenerate_room", bind=True, max_retries=2)
def regenerate_room_task(self, project_id: str, room_id: str, feedback: str):
    """Re-run a rejected room's pipeline with human feedback.

    The feedback string is stored on the room state so that downstream agents
    (particularly Agent 2 - Planner) can incorporate it into revised prompts.
    """
    from pipeline.orchestrator import PipelineOrchestrator
    from pipeline.state import StateManager

    logger.info(
        "Celery task regenerate_room: project=%s room=%s feedback=%r",
        project_id,
        room_id,
        feedback[:120],
    )

    async def _regenerate():
        state = StateManager()
        orchestrator = PipelineOrchestrator()

        # Record feedback and bump rejection count
        ps = await state.get_pipeline_state(project_id)
        for room in ps.rooms:
            if room.room_id == room_id:
                room.rejection_count += 1
                room.rejection_feedback = feedback
                break

        await state.update_room_state(project_id, room_id, {
            "status": "pending",
            "rejection_feedback": feedback,
        })

        # Re-run room pipeline
        await orchestrator.run_single_room(project_id, room_id)

    try:
        _run_async(_regenerate())
    except Exception as exc:
        logger.exception(
            "Regenerate task failed: project=%s room=%s", project_id, room_id
        )
        raise self.retry(exc=exc, countdown=60) if self.request.retries < self.max_retries else exc
