"""FurniVision AI -- Output retrieval routes."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import (
    GCS_PATH_HERO_RENDERS,
    GCS_PATH_VIDEO,
    GCS_PATH_HLS,
    GCS_PATH_VIEWER_MANIFEST,
    GCS_PATH_REPORT,
    GCS_PATH_MASTER_VIDEO,
)
from pipeline.state import StateManager
from services.storage import StorageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects/{project_id}/outputs", tags=["outputs"])

_state = StateManager()

# Lazy-initialised storage
_storage: StorageService | None = None


def _get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RoomOutputs(BaseModel):
    room_id: str
    label: str
    hero_renders: list[str]
    video_url: str | None
    hls_url: str | None
    viewer_manifest_url: str | None
    preview_url: str | None
    qc_score: float | None


class ProjectOutputsResponse(BaseModel):
    project_id: str
    status: str
    rooms: list[RoomOutputs]
    report_pdf_url: str | None
    master_video_url: str | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=ProjectOutputsResponse)
async def get_outputs(project_id: str):
    """Return all output URLs (hero renders, video, HLS, viewer manifest, report PDF).

    Generates signed URLs for each available output asset.
    """
    # Validate project
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Load pipeline state for room details
    try:
        ps = await _state.get_pipeline_state(project_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="No pipeline state found. The pipeline has not been run yet.",
        )

    storage = _get_storage()

    # Build per-room output URLs
    room_outputs: list[RoomOutputs] = []
    for room_state in ps.rooms:
        room_id = room_state.room_id

        # Hero renders -- try to generate signed URLs for available renders
        hero_urls: list[str] = []
        if room_state.hero_frame_urls:
            for url_or_path in room_state.hero_frame_urls:
                try:
                    signed = storage.get_signed_url(url_or_path)
                    hero_urls.append(signed)
                except Exception:
                    logger.debug("Could not sign hero render URL: %s", url_or_path)
                    hero_urls.append(url_or_path)
        else:
            # Try standard GCS paths for hero renders (up to 4)
            for n in range(4):
                gcs_path = GCS_PATH_HERO_RENDERS.format(
                    project_id=project_id, room_id=room_id, n=n
                )
                try:
                    signed = storage.get_signed_url(gcs_path)
                    hero_urls.append(signed)
                except Exception:
                    break

        # Video URL
        video_url = _safe_sign(
            storage,
            room_state.video_url
            or GCS_PATH_VIDEO.format(project_id=project_id, room_id=room_id),
        )

        # HLS URL
        hls_url = _safe_sign(
            storage,
            GCS_PATH_HLS.format(project_id=project_id, room_id=room_id),
        )

        # Viewer manifest
        manifest_url = _safe_sign(
            storage,
            GCS_PATH_VIEWER_MANIFEST.format(
                project_id=project_id, room_id=room_id
            ),
        )

        # Preview
        preview_url = None
        if room_state.preview_url:
            preview_url = _safe_sign(storage, room_state.preview_url)

        room_outputs.append(
            RoomOutputs(
                room_id=room_id,
                label=room_state.label,
                hero_renders=hero_urls,
                video_url=video_url,
                hls_url=hls_url,
                viewer_manifest_url=manifest_url,
                preview_url=preview_url,
                qc_score=room_state.qc_score,
            )
        )

    # Project-level outputs
    report_url = _safe_sign(
        storage,
        GCS_PATH_REPORT.format(project_id=project_id),
    )
    master_video_url = _safe_sign(
        storage,
        GCS_PATH_MASTER_VIDEO.format(project_id=project_id),
    )

    return ProjectOutputsResponse(
        project_id=project_id,
        status=project.status,
        rooms=room_outputs,
        report_pdf_url=report_url,
        master_video_url=master_video_url,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_sign(storage: StorageService, gcs_path: str) -> str | None:
    """Attempt to generate a signed URL; return None on failure."""
    try:
        return storage.get_signed_url(gcs_path)
    except Exception:
        logger.debug("Could not sign GCS path: %s", gcs_path)
        return None
