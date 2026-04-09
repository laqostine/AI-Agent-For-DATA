"""FurniVision AI — Image edit endpoint for human-in-the-loop feedback.

Takes an existing room render + text feedback + optional product reference
images and produces a targeted edit using Gemini Flash Image.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import TEMP_DIR
from services.imagen import ImagenService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["edit"])


class ImageEditRequest(BaseModel):
    project_id: str
    room_id: str
    image_id: str  # GeneratedImage.id of the image to edit
    feedback: str  # Human feedback text
    product_ids: list[str] = []  # Optional product IDs for reference


class ImageEditResponse(BaseModel):
    edited_image_id: str
    edited_image_path: str
    feedback_applied: str


@router.post("/projects/{project_id}/rooms/{room_id}/edit-image")
async def edit_room_image(
    project_id: str,
    room_id: str,
    request: ImageEditRequest,
) -> ImageEditResponse:
    """Apply targeted edits to a room render based on human feedback.

    Uses Gemini Flash Image to modify specific elements while preserving
    the overall composition.
    """
    from pipeline.state import StateManager

    state = StateManager()

    # Load the project to find the room and image
    try:
        project = await state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the room
    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    # Find the source image
    source_image = next(
        (img for img in room.generated_images if img.id == request.image_id), None
    )
    if source_image is None:
        raise HTTPException(
            status_code=404, detail=f"Image {request.image_id} not found in room"
        )

    # Load the source image bytes
    source_path = Path(source_image.image_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source image file not found on disk")
    source_bytes = source_path.read_bytes()

    # Load product reference images if specified
    ref_images: list[bytes] = []
    if request.product_ids:
        for prod in room.products:
            if prod.id in request.product_ids and prod.image_path:
                ref_path = Path(prod.image_path)
                if ref_path.exists():
                    ref_images.append(ref_path.read_bytes())

    # Apply the edit (retry once on transient failure)
    import asyncio as _asyncio
    imagen = ImagenService()
    edited_bytes: bytes | None = None
    for attempt in range(1, 3):
        try:
            edited_bytes = await imagen.edit_image_with_feedback(
                current_image=source_bytes,
                feedback=request.feedback,
                reference_images=ref_images if ref_images else None,
            )
            break
        except Exception as exc:
            logger.warning("Image edit attempt %d failed for room %s: %s", attempt, room_id, exc)
            if attempt == 2:
                raise HTTPException(status_code=500, detail="Image edit failed after retries")
            await _asyncio.sleep(2)

    # Save the edited image
    output_dir = TEMP_DIR / "storage" / f"projects/{project_id}/rooms/{room_id}/images"
    output_dir.mkdir(parents=True, exist_ok=True)

    edited_id = str(uuid.uuid4())[:8]
    version = len(room.generated_images) + 1
    edited_path = output_dir / f"edited_v{version}_{edited_id}.png"
    edited_path.write_bytes(edited_bytes)

    # Update project state with new image
    from models.project import GeneratedImage

    new_image = GeneratedImage(
        id=edited_id,
        room_id=room_id,
        image_path=str(edited_path),
        prompt_used=f"Edit: {request.feedback}",
        version=version,
        type="edited",
    )
    room.generated_images.append(new_image)
    room.feedback.append(request.feedback)

    # Save back to state
    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await state.update_project(project_id, {"v5_rooms": rooms_data})

    logger.info(
        "Image edit complete: project=%s, room=%s, edited=%s",
        project_id, room_id, edited_id,
    )

    return ImageEditResponse(
        edited_image_id=edited_id,
        edited_image_path=str(edited_path),
        feedback_applied=request.feedback,
    )
