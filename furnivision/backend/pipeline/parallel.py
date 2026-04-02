"""FurniVision AI -- Parallel room processing engine (Phase 2).

Runs the Agent 2->3->4->5 chain for every room concurrently using
``asyncio.gather``, so all rooms are processed in parallel rather than
sequentially.
"""

import asyncio
import logging
from datetime import datetime

from models.project import ProjectBrief, RoomGeometry, FurnitureItem
from models.pipeline import PipelineState, RoomPipelineState, FrameStatus
from pipeline.state import StateManager
from config import FRAMES_PER_ROOM, MAX_CONCURRENT_IMAGEN_CALLS

logger = logging.getLogger(__name__)


class ParallelRoomEngine:
    """Process multiple rooms concurrently through the agent pipeline."""

    def __init__(self) -> None:
        self.state = StateManager()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGEN_CALLS)

    async def process_all_rooms(
        self,
        project_id: str,
        rooms: list[RoomGeometry],
        furniture_items: list[FurnitureItem],
        brief: ProjectBrief,
    ) -> dict[str, str]:
        """Run agents 2-5 for all rooms concurrently.

        Args:
            project_id: The project identifier.
            rooms: List of rooms to process.
            furniture_items: All furniture items (will be filtered per room).
            brief: The project brief with style/environment parameters.

        Returns:
            A dict mapping ``room_id`` to final status (``"complete"`` or ``"failed"``).
        """
        if not rooms:
            logger.warning("No rooms to process for project %s", project_id)
            return {}

        logger.info(
            "Starting parallel processing of %d rooms for project %s",
            len(rooms),
            project_id,
        )

        # Initialise pipeline room states
        room_states = [
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
            for room in rooms
        ]
        await self.state.update_pipeline_state(
            project_id,
            {"rooms": [rs.model_dump() for rs in room_states]},
        )

        # Build tasks
        tasks = []
        for room in rooms:
            room_furniture = room.furniture_items
            tasks.append(
                self._process_single_room(
                    project_id, room, room_furniture, brief
                )
            )

        # Run all rooms concurrently, collecting results even if some fail
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, str] = {}
        for room, result in zip(rooms, results_raw):
            if isinstance(result, Exception):
                logger.error(
                    "Room %s failed in parallel processing: %s",
                    room.id,
                    result,
                )
                results[room.id] = "failed"
            else:
                results[room.id] = "complete"

        succeeded = sum(1 for v in results.values() if v == "complete")
        failed = sum(1 for v in results.values() if v == "failed")
        logger.info(
            "Parallel room processing finished for project %s: %d succeeded, %d failed",
            project_id,
            succeeded,
            failed,
        )
        return results

    async def _process_single_room(
        self,
        project_id: str,
        room: RoomGeometry,
        furniture_items: list[FurnitureItem],
        brief: ProjectBrief,
    ) -> None:
        """Run agents 2->3->4->5 for one room, guarded by a concurrency semaphore."""
        async with self._semaphore:
            from pipeline.orchestrator import PipelineOrchestrator

            orchestrator = PipelineOrchestrator()
            await orchestrator._run_room_pipeline(
                project_id=project_id,
                room_id=room.id,
                room=room,
                furniture_items=furniture_items,
                brief=brief,
            )
