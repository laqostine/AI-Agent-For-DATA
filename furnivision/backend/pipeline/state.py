"""FurniVision AI — Pipeline state management backed by Google Firestore."""

import logging
from datetime import datetime
from typing import Any

from models.project import Project
from models.pipeline import PipelineState, RoomPipelineState, FrameStatus
from models.extraction import ExtractionResult
from config import FIRESTORE_DATABASE, GOOGLE_CLOUD_PROJECT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback store (used when Firestore is unavailable in dev)
# ---------------------------------------------------------------------------

_MEMORY_STORE: dict[str, dict[str, Any]] = {}


class StateManager:
    """Manages project, pipeline, and extraction state in Firestore.

    Falls back to an in-memory dict when Firestore is not available (e.g.
    local development without credentials).
    """

    def __init__(self) -> None:
        self._db: Any = None
        self._use_memory = False
        try:
            from google.cloud.firestore_v1 import AsyncClient  # type: ignore[import-untyped]

            self._db = AsyncClient(
                project=GOOGLE_CLOUD_PROJECT or None,
                database=FIRESTORE_DATABASE,
            )
            logger.info(
                "StateManager initialised with Firestore (database=%s)",
                FIRESTORE_DATABASE,
            )
        except Exception:
            logger.warning(
                "Firestore client unavailable — falling back to in-memory store. "
                "This is acceptable for local development but MUST NOT be used in production."
            )
            self._use_memory = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mem_key(self, *parts: str) -> str:
        return "/".join(parts)

    async def _fs_set(self, collection: str, doc_id: str, data: dict) -> None:
        """Set a Firestore document (create or overwrite)."""
        if self._use_memory:
            _MEMORY_STORE[self._mem_key(collection, doc_id)] = data
            return
        await self._db.collection(collection).document(doc_id).set(data)

    async def _fs_get(self, collection: str, doc_id: str) -> dict | None:
        """Get a Firestore document as a dict, or None."""
        if self._use_memory:
            return _MEMORY_STORE.get(self._mem_key(collection, doc_id))
        snap = await self._db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    async def _fs_update(self, collection: str, doc_id: str, data: dict) -> None:
        """Merge-update fields on an existing Firestore document."""
        if self._use_memory:
            key = self._mem_key(collection, doc_id)
            existing = _MEMORY_STORE.get(key, {})
            existing.update(data)
            _MEMORY_STORE[key] = existing
            return
        await self._db.collection(collection).document(doc_id).update(data)

    @staticmethod
    def _serialize_datetime(obj: Any) -> Any:
        """Recursively convert datetime objects to ISO strings for storage."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: StateManager._serialize_datetime(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [StateManager._serialize_datetime(v) for v in obj]
        return obj

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    async def create_project(self, project: Project) -> str:
        """Persist a new project. Returns the project id."""
        data = self._serialize_datetime(project.model_dump())
        await self._fs_set("projects", project.id, data)
        logger.info("Created project %s", project.id)
        return project.id

    async def get_project(self, project_id: str) -> Project:
        """Load a project by id. Raises ValueError if not found."""
        data = await self._fs_get("projects", project_id)
        if data is None:
            raise ValueError(f"Project {project_id} not found")
        return Project(**data)

    async def update_project(self, project_id: str, data: dict) -> None:
        """Merge-update fields on an existing project document."""
        data["updated_at"] = datetime.utcnow().isoformat()
        serialized = self._serialize_datetime(data)
        await self._fs_update("projects", project_id, serialized)
        logger.info("Updated project %s: keys=%s", project_id, list(data.keys()))

    # ------------------------------------------------------------------
    # Extraction result
    # ------------------------------------------------------------------

    async def save_extraction(self, project_id: str, extraction: ExtractionResult) -> None:
        """Save the Agent 1 extraction result under the project."""
        data = self._serialize_datetime(extraction.model_dump())
        await self._fs_set("extractions", project_id, data)
        logger.info("Saved extraction for project %s", project_id)

    async def get_extraction(self, project_id: str) -> ExtractionResult:
        """Load the extraction result. Raises ValueError if not found."""
        data = await self._fs_get("extractions", project_id)
        if data is None:
            raise ValueError(f"Extraction for project {project_id} not found")
        return ExtractionResult(**data)

    # ------------------------------------------------------------------
    # Pipeline state
    # ------------------------------------------------------------------

    async def create_pipeline_state(self, state: PipelineState) -> None:
        """Persist a new pipeline state document."""
        data = self._serialize_datetime(state.model_dump())
        await self._fs_set("pipeline_states", state.project_id, data)
        logger.info("Created pipeline state for project %s (job=%s)", state.project_id, state.job_id)

    async def get_pipeline_state(self, project_id: str) -> PipelineState:
        """Load the pipeline state. Raises ValueError if not found."""
        data = await self._fs_get("pipeline_states", project_id)
        if data is None:
            raise ValueError(f"Pipeline state for project {project_id} not found")
        return PipelineState(**data)

    async def update_pipeline_state(self, project_id: str, data: dict) -> None:
        """Merge-update fields on the pipeline state."""
        serialized = self._serialize_datetime(data)
        await self._fs_update("pipeline_states", project_id, serialized)
        logger.debug("Updated pipeline state for %s: keys=%s", project_id, list(data.keys()))

    async def update_room_state(self, project_id: str, room_id: str, data: dict) -> None:
        """Update a specific room's pipeline state within the rooms array.

        Loads the full pipeline state, finds the room, merges data, and saves back.
        """
        ps = await self.get_pipeline_state(project_id)
        updated = False
        for room in ps.rooms:
            if room.room_id == room_id:
                for key, value in data.items():
                    setattr(room, key, value)
                updated = True
                break
        if not updated:
            logger.warning("Room %s not found in pipeline state for project %s", room_id, project_id)
            return
        await self._fs_set("pipeline_states", project_id, self._serialize_datetime(ps.model_dump()))
        logger.debug("Updated room %s state in project %s", room_id, project_id)

    async def update_frame_status(
        self, project_id: str, room_id: str, frame_idx: int, status: dict
    ) -> None:
        """Update a single frame's status within a room's pipeline state."""
        ps = await self.get_pipeline_state(project_id)
        for room in ps.rooms:
            if room.room_id == room_id:
                for frame in room.frames:
                    if frame.frame_idx == frame_idx:
                        for key, value in status.items():
                            setattr(frame, key, value)
                        break
                break
        await self._fs_set("pipeline_states", project_id, self._serialize_datetime(ps.model_dump()))
        logger.debug("Updated frame %d in room %s for project %s", frame_idx, room_id, project_id)

    # ------------------------------------------------------------------
    # Gate confirmation
    # ------------------------------------------------------------------

    async def set_gate_confirmed(self, project_id: str, gate: int, confirmed: bool) -> None:
        """Mark a human-review gate as confirmed or not."""
        field = f"gate_{gate}_confirmed"
        if gate == 1:
            await self.update_pipeline_state(project_id, {"gate_1_confirmed": confirmed})
        elif gate == 2:
            # Gate 2 is per-room; this sets a global override
            await self.update_pipeline_state(project_id, {"gate_2_all_confirmed": confirmed})
        else:
            raise ValueError(f"Unknown gate number: {gate}")
        logger.info("Gate %d set to %s for project %s", gate, confirmed, project_id)

    async def is_gate_confirmed(self, project_id: str, gate: int) -> bool:
        """Check whether a gate has been confirmed."""
        ps = await self.get_pipeline_state(project_id)
        if gate == 1:
            return ps.gate_1_confirmed
        if gate == 2:
            # Gate 2 is confirmed when ALL rooms have been approved
            if not ps.gate_2_rooms_approved:
                return False
            return all(ps.gate_2_rooms_approved.values())
        raise ValueError(f"Unknown gate number: {gate}")
