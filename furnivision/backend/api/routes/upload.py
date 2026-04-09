"""FurniVision AI -- File upload routes (floorplan PDF and furniture images)."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from config import TEMP_DIR, GCS_PATH_FLOORPLAN, GCS_PATH_FURNITURE, GCS_PATH_REFERENCE
from pipeline.state import StateManager
from services.storage import StorageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects/{project_id}/upload", tags=["upload"])

_state = StateManager()

# Lazy-initialised storage (avoids crash when GCS creds are absent at import)
_storage: StorageService | None = None


def _get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage


# ---------------------------------------------------------------------------
# Accepted file types
# ---------------------------------------------------------------------------

_FLOORPLAN_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/acad",           # DWG
    "application/x-acad",
    "application/dwg",
    "image/vnd.dwg",
}

_FURNITURE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class FloorplanUploadResponse(BaseModel):
    file_id: str
    gcs_path: str


class FurnitureFileInfo(BaseModel):
    file_id: str
    filename: str
    gcs_path: str


class FurnitureUploadResponse(BaseModel):
    files: list[FurnitureFileInfo]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/floorplan", response_model=FloorplanUploadResponse, status_code=201)
async def upload_floorplan(project_id: str, file: UploadFile = File(...)):
    """Upload a floorplan file (PDF, PNG, JPG, or DWG) to GCS."""

    # Validate project exists
    try:
        await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Validate content type
    content_type = file.content_type or ""
    if content_type not in _FLOORPLAN_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported floorplan file type: {content_type}. "
            f"Accepted: PDF, PNG, JPG, DWG.",
        )

    file_id = str(uuid.uuid4())

    # Determine extension
    original_name = file.filename or "floorplan"
    ext = Path(original_name).suffix.lower() or ".pdf"

    # Read file contents
    try:
        contents = await file.read()
    except Exception:
        logger.exception("Failed to read uploaded floorplan for project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to read uploaded file")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Build GCS path
    gcs_path = GCS_PATH_FLOORPLAN.format(project_id=project_id)
    if ext != ".pdf":
        gcs_path = gcs_path.replace(".pdf", ext)

    # Upload
    try:
        storage = _get_storage()
        await storage.upload_bytes(contents, gcs_path, content_type=content_type)
    except Exception:
        logger.exception("GCS upload failed for floorplan: project=%s", project_id)
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")

    # Update project record
    try:
        await _state.update_project(project_id, {"floorplan_gcs_path": gcs_path})
    except Exception:
        logger.exception("Failed to update project with floorplan path")

    logger.info("Floorplan uploaded: project=%s path=%s", project_id, gcs_path)

    return FloorplanUploadResponse(file_id=file_id, gcs_path=gcs_path)


@router.post("/furniture", response_model=FurnitureUploadResponse, status_code=201)
async def upload_furniture(
    project_id: str,
    files: list[UploadFile] = File(...),
):
    """Upload one or more furniture images to GCS."""

    # Validate project exists
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    storage = _get_storage()
    uploaded: list[FurnitureFileInfo] = []
    furniture_gcs_entries: list[dict] = list(project.furniture_gcs_paths)

    for upload_file in files:
        content_type = upload_file.content_type or ""
        if content_type not in _FURNITURE_CONTENT_TYPES:
            logger.warning(
                "Skipping unsupported furniture file %s (type=%s)",
                upload_file.filename,
                content_type,
            )
            continue

        file_id = str(uuid.uuid4())
        original_name = upload_file.filename or f"furniture_{file_id}.png"
        ext = Path(original_name).suffix.lower() or ".png"

        try:
            contents = await upload_file.read()
        except Exception:
            logger.exception("Failed to read furniture file %s", original_name)
            continue

        if not contents:
            logger.warning("Skipping empty furniture file %s", original_name)
            continue

        gcs_path = GCS_PATH_FURNITURE.format(
            project_id=project_id,
            item_id=file_id,
        )
        # Ensure correct extension
        if not gcs_path.endswith(ext):
            gcs_path = gcs_path.rsplit(".", 1)[0] + ext

        try:
            await storage.upload_bytes(contents, gcs_path, content_type=content_type)
        except Exception:
            logger.exception("GCS upload failed for furniture file %s", original_name)
            continue

        info = FurnitureFileInfo(
            file_id=file_id,
            filename=original_name,
            gcs_path=gcs_path,
        )
        uploaded.append(info)
        furniture_gcs_entries.append({
            "id": file_id,
            "filename": original_name,
            "gcs_path": gcs_path,
        })

    if not uploaded:
        raise HTTPException(
            status_code=400,
            detail="No valid furniture images were uploaded",
        )

    # Persist updated furniture paths on the project
    try:
        await _state.update_project(project_id, {
            "furniture_gcs_paths": furniture_gcs_entries,
        })
    except Exception:
        logger.exception("Failed to update project with furniture paths")

    logger.info(
        "Furniture uploaded: project=%s count=%d",
        project_id,
        len(uploaded),
    )

    return FurnitureUploadResponse(files=uploaded)


class ReferenceUploadResponse(BaseModel):
    files: list[FurnitureFileInfo]


@router.post("/reference", response_model=ReferenceUploadResponse, status_code=201)
async def upload_reference(
    project_id: str,
    files: list[UploadFile] = File(...),
):
    """Upload one or more reference render images (existing room visualizations).

    These are used to anchor Imagen 4 and Veo 3 generation so outputs
    match the actual room design intent — same proportions, furniture, materials.
    """
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    storage = _get_storage()
    uploaded: list[FurnitureFileInfo] = []
    reference_entries: list[dict] = list(project.reference_render_gcs_paths)

    for upload_file in files:
        content_type = upload_file.content_type or ""
        if content_type not in _FURNITURE_CONTENT_TYPES:
            logger.warning("Skipping unsupported reference file %s", upload_file.filename)
            continue

        item_id = str(uuid.uuid4())
        original_name = upload_file.filename or f"reference_{item_id}.jpg"
        ext = Path(original_name).suffix.lower() or ".jpg"

        try:
            contents = await upload_file.read()
        except Exception:
            logger.exception("Failed to read reference file %s", original_name)
            continue

        if not contents:
            continue

        gcs_path = GCS_PATH_REFERENCE.format(project_id=project_id, item_id=item_id)
        if not gcs_path.endswith(ext):
            gcs_path = gcs_path.rsplit(".", 1)[0] + ext

        try:
            await storage.upload_bytes(contents, gcs_path, content_type=content_type)
        except Exception:
            logger.exception("Storage upload failed for reference file %s", original_name)
            continue

        info = FurnitureFileInfo(file_id=item_id, filename=original_name, gcs_path=gcs_path)
        uploaded.append(info)
        reference_entries.append({"id": item_id, "filename": original_name, "gcs_path": gcs_path})

    if not uploaded:
        raise HTTPException(status_code=400, detail="No valid reference images uploaded")

    try:
        await _state.update_project(project_id, {"reference_render_gcs_paths": reference_entries})
    except Exception:
        logger.exception("Failed to update project with reference paths")

    logger.info("Reference renders uploaded: project=%s count=%d", project_id, len(uploaded))
    return ReferenceUploadResponse(files=uploaded)
