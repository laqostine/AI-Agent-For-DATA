"""FurniVision AI — V5 Human-in-the-Loop API routes.

Handles the full V5 workflow:
  - PPTX upload & extraction
  - Extraction review (Gate 1)
  - Image generation & review (Gate 2)
  - Video generation & compilation
  - Final download
"""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import TEMP_DIR
from models.project import (
    FloorPlan,
    GeneratedImage,
    Product,
    Project,
    V5Room,
)
from pipeline.state import StateManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/v5/projects", tags=["v5"])

_state = StateManager()

# Keep references to background tasks to prevent garbage collection
_BACKGROUND_TASKS: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateV5ProjectResponse(BaseModel):
    project_id: str
    status: str


class ExtractionResponse(BaseModel):
    project_id: str
    status: str
    rooms: list[dict]
    floor_plans: list[dict]
    total_products: int


class UpdateRoomRequest(BaseModel):
    label: str | None = None
    products: list[dict] | None = None  # [{id, name, dimensions, image_path}]


class SwapProductRequest(BaseModel):
    old_product_id: str
    new_product_image_path: str
    new_product_name: str | None = None


class RegionSelect(BaseModel):
    x: float  # 0.0-1.0 relative to image width
    y: float  # 0.0-1.0 relative to image height
    width: float
    height: float


class FeedbackRequest(BaseModel):
    feedback: str
    product_ids: list[str] = []
    region: RegionSelect | None = None  # Optional region to constrain edit


class RoomImageResponse(BaseModel):
    room_id: str
    images: list[dict]


class CompileRequest(BaseModel):
    room_order: list[str] | None = None  # Optional custom room ordering


class FinalVideoResponse(BaseModel):
    project_id: str
    video_path: str
    status: str


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateV5ProjectResponse)
async def create_v5_project(name: str = "New Project"):
    """Create a new V5 project."""
    project_id = str(uuid.uuid4())[:12]
    project = Project(
        id=project_id,
        name=name,
        status="uploading",
    )
    await _state.create_project(project)
    logger.info("Created V5 project: %s", project_id)
    return CreateV5ProjectResponse(project_id=project_id, status="uploading")


@router.get("/{project_id}")
async def get_v5_project(project_id: str):
    """Get full project state."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


# ---------------------------------------------------------------------------
# Upload & Extract
# ---------------------------------------------------------------------------


@router.post("/{project_id}/upload-spec")
async def upload_spec(project_id: str, file: UploadFile = File(...)):
    """Upload a PPTX spec file and trigger extraction."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file type
    filename = file.filename or "spec.pptx"
    if not filename.lower().endswith((".pptx", ".ppt")):
        raise HTTPException(status_code=400, detail="Only PPTX files are supported")

    # Save file locally (100MB limit)
    spec_dir = TEMP_DIR / "storage" / f"projects/{project_id}/spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / filename
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PPTX file too large (max 100MB)")
    spec_path.write_bytes(content)

    await _state.update_project(project_id, {
        "spec_file_path": str(spec_path),
        "status": "extracting",
    })

    logger.info("Spec uploaded for project %s: %s (%d bytes)", project_id, filename, len(content))

    # Trigger extraction in background (keep reference to prevent GC)
    task = asyncio.create_task(_run_extraction(project_id, str(spec_path)))
    _BACKGROUND_TASKS[project_id] = task
    task.add_done_callback(lambda t: _BACKGROUND_TASKS.pop(project_id, None))

    return {"project_id": project_id, "status": "extracting", "filename": filename}


@router.post("/{project_id}/upload-logo")
async def upload_logo(project_id: str, file: UploadFile = File(...)):
    """Upload a company logo for the video end card."""
    try:
        await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    assets_dir = TEMP_DIR / "storage" / f"projects/{project_id}/assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    logo_path = assets_dir / (file.filename or "logo.png")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Logo file too large (max 10MB)")
    logo_path.write_bytes(content)

    await _state.update_project(project_id, {"logo_path": str(logo_path)})
    return {"logo_path": str(logo_path)}


@router.post("/{project_id}/upload-music")
async def upload_music(project_id: str, file: UploadFile = File(...)):
    """Upload background music for the final video."""
    try:
        await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    assets_dir = TEMP_DIR / "storage" / f"projects/{project_id}/assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    music_path = assets_dir / (file.filename or "music.mp3")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Music file too large (max 50MB)")
    music_path.write_bytes(content)

    await _state.update_project(project_id, {"music_path": str(music_path)})
    return {"music_path": str(music_path)}


# ---------------------------------------------------------------------------
# Extraction results
# ---------------------------------------------------------------------------


@router.get("/{project_id}/extraction")
async def get_extraction(project_id: str):
    """Get extraction results for review.

    Returns the current project rooms/products. During extraction, returns
    partial data with extracting status (not an error).
    """
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    floor_plans_data = [fp.model_dump() for fp in project.floor_plans]
    total_products = sum(len(r.products) for r in project.v5_rooms)

    return {
        "project_id": project_id,
        "status": project.status,
        "rooms": rooms_data,
        "floor_plans": floor_plans_data,
        "total_products": total_products,
    }


# ---------------------------------------------------------------------------
# Gate 1: Extraction Review
# ---------------------------------------------------------------------------


@router.put("/{project_id}/rooms/{room_id}")
async def update_room(project_id: str, room_id: str, body: UpdateRoomRequest):
    """Edit a room's name or products during extraction review."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    if body.label is not None:
        room.label = body.label
    if body.products is not None:
        room.products = [Product(**p) for p in body.products]

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {"v5_rooms": rooms_data})

    return {"room_id": room_id, "status": "updated"}


@router.post("/{project_id}/rooms/{room_id}/swap-product")
async def swap_product(project_id: str, room_id: str, body: SwapProductRequest):
    """Swap a product image within a room."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    product = next((p for p in room.products if p.id == body.old_product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {body.old_product_id} not found")

    product.image_path = body.new_product_image_path
    if body.new_product_name:
        product.name = body.new_product_name

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {"v5_rooms": rooms_data})

    return {"room_id": room_id, "product_id": product.id, "status": "swapped"}


@router.post("/{project_id}/approve-extraction")
async def approve_extraction(project_id: str):
    """Approve extraction and trigger image generation for all rooms."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.v5_rooms:
        raise HTTPException(status_code=400, detail="No rooms to process")

    # Mark all rooms as approved
    for room in project.v5_rooms:
        room.status = "approved"

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {
        "v5_rooms": rooms_data,
        "status": "generating_images",
    })

    # Trigger image generation in background
    task = asyncio.create_task(_run_image_generation(project_id))
    _BACKGROUND_TASKS[f"{project_id}_img"] = task
    task.add_done_callback(lambda t: _BACKGROUND_TASKS.pop(f"{project_id}_img", None))

    logger.info("Extraction approved for project %s: %d rooms", project_id, len(project.v5_rooms))
    return {
        "project_id": project_id,
        "status": "generating_images",
        "rooms_count": len(project.v5_rooms),
    }


# ---------------------------------------------------------------------------
# Image Generation & Review (Gate 2)
# ---------------------------------------------------------------------------


@router.get("/{project_id}/rooms/{room_id}/images", response_model=RoomImageResponse)
async def get_room_images(project_id: str, room_id: str):
    """Get generated images for a room."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    return RoomImageResponse(
        room_id=room_id,
        images=[img.model_dump() for img in room.generated_images],
    )


@router.post("/{project_id}/rooms/{room_id}/regenerate")
async def regenerate_room(project_id: str, room_id: str):
    """Re-generate room images from scratch."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    room.status = "generating"
    room.generated_images = []  # Clear previous images

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {"v5_rooms": rooms_data})

    # Trigger regeneration in background
    task = asyncio.create_task(_run_single_room_generation(project_id, room_id))
    _BACKGROUND_TASKS[f"{project_id}_{room_id}_regen"] = task
    task.add_done_callback(lambda t: _BACKGROUND_TASKS.pop(f"{project_id}_{room_id}_regen", None))

    return {"room_id": room_id, "status": "generating"}


@router.post("/{project_id}/rooms/{room_id}/feedback")
async def submit_room_feedback(
    project_id: str, room_id: str, body: FeedbackRequest
):
    """Submit text feedback for a room image → triggers AI edit."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    if not room.generated_images:
        raise HTTPException(status_code=400, detail="No images to edit")

    # Use the latest image for editing
    latest_image = room.generated_images[-1]

    # Trigger edit via the edit endpoint logic
    from services.imagen import ImagenService

    source_path = Path(latest_image.image_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source image not found")

    source_bytes = source_path.read_bytes()

    # Load product reference images
    ref_images: list[bytes] = []
    for prod in room.products:
        if body.product_ids and prod.id not in body.product_ids:
            continue
        if prod.image_path and Path(prod.image_path).exists():
            ref_images.append(Path(prod.image_path).read_bytes())

    imagen = ImagenService()
    try:
        edited_bytes = await imagen.edit_image_with_feedback(
            current_image=source_bytes,
            feedback=body.feedback,
            reference_images=ref_images if ref_images else None,
            region=body.region.model_dump() if body.region else None,
        )
    except Exception as exc:
        logger.exception("Image edit failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Image edit failed: {exc}")

    # Save edited image
    output_dir = TEMP_DIR / "storage" / f"projects/{project_id}/rooms/{room_id}/images"
    output_dir.mkdir(parents=True, exist_ok=True)
    edited_id = str(uuid.uuid4())[:8]
    version = len(room.generated_images) + 1
    edited_path = output_dir / f"edited_v{version}_{edited_id}.png"
    edited_path.write_bytes(edited_bytes)

    new_image = GeneratedImage(
        id=edited_id,
        room_id=room_id,
        image_path=str(edited_path),
        prompt_used=f"Edit: {body.feedback}",
        version=version,
        type="edited",
    )
    room.generated_images.append(new_image)
    room.feedback.append(body.feedback)

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {"v5_rooms": rooms_data})

    return {
        "room_id": room_id,
        "edited_image_id": edited_id,
        "edited_image_path": str(edited_path),
        "version": version,
    }


@router.post("/{project_id}/rooms/{room_id}/approve")
async def approve_room_image(project_id: str, room_id: str):
    """Approve a room's generated image (Gate 2)."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    room = next((r for r in project.v5_rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    room.status = "image_approved"

    rooms_data = [r.model_dump() for r in project.v5_rooms]
    await _state.update_project(project_id, {"v5_rooms": rooms_data})

    # Check if all rooms are approved
    all_approved = all(r.status == "image_approved" for r in project.v5_rooms)
    if all_approved:
        await _state.update_project(project_id, {"status": "reviewing_images"})

    logger.info("Room %s image approved for project %s", room_id, project_id)
    return {
        "room_id": room_id,
        "status": "image_approved",
        "all_approved": all_approved,
    }


# ---------------------------------------------------------------------------
# Video Generation & Compilation
# ---------------------------------------------------------------------------


class GenerateVideosRequest(BaseModel):
    video_mode: str = "standard"  # "standard" (MiniMax $0.27) or "premium" (Kling $0.49)


@router.post("/{project_id}/generate-videos")
async def generate_videos(project_id: str, body: GenerateVideosRequest | None = None):
    """Generate walkthrough videos for all approved rooms."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    approved_rooms = [r for r in project.v5_rooms if r.status == "image_approved"]
    if not approved_rooms:
        raise HTTPException(status_code=400, detail="No approved rooms to generate videos for")

    video_mode = (body.video_mode if body else "standard")
    if video_mode not in ("standard", "premium"):
        raise HTTPException(status_code=400, detail="video_mode must be 'standard' or 'premium'")

    await _state.update_project(project_id, {"status": "generating_videos"})

    # Trigger video generation in background
    task = asyncio.create_task(_run_video_generation(project_id, video_mode=video_mode))
    _BACKGROUND_TASKS[f"{project_id}_video"] = task
    task.add_done_callback(lambda t: _BACKGROUND_TASKS.pop(f"{project_id}_video", None))

    return {
        "project_id": project_id,
        "status": "generating_videos",
        "rooms_count": len(approved_rooms),
        "video_mode": video_mode,
    }


@router.post("/{project_id}/compile", response_model=FinalVideoResponse)
async def compile_final_video(project_id: str, body: CompileRequest | None = None):
    """Compile all room videos into the final deliverable."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    rooms_with_video = [r for r in project.v5_rooms if r.video_path]
    if not rooms_with_video:
        raise HTTPException(status_code=400, detail="No room videos available")

    # Order rooms
    if body and body.room_order:
        order_map = {rid: i for i, rid in enumerate(body.room_order)}
        rooms_with_video.sort(key=lambda r: order_map.get(r.id, 999))

    video_paths = [r.video_path for r in rooms_with_video if r.video_path]

    from services.video_compiler import VideoCompiler

    compiler = VideoCompiler()
    output_dir = TEMP_DIR / "storage" / f"projects/{project_id}/final"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "final_walkthrough.mp4")

    try:
        await compiler.compile(
            room_video_paths=video_paths,
            output_path=output_path,
            logo_path=project.logo_path,
            music_path=project.music_path,
        )
    except Exception as exc:
        logger.exception("Video compilation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Compilation failed: {exc}")

    await _state.update_project(project_id, {
        "final_video_path": output_path,
        "status": "complete",
    })

    return FinalVideoResponse(
        project_id=project_id,
        video_path=output_path,
        status="complete",
    )


@router.get("/{project_id}/final-video")
async def get_final_video(project_id: str):
    """Download the final compiled video."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.final_video_path:
        raise HTTPException(status_code=404, detail="No final video available")

    video_path = Path(project.final_video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    from fastapi.responses import FileResponse

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{project.name}_walkthrough.mp4",
    )


# ---------------------------------------------------------------------------
# Background task runners
# ---------------------------------------------------------------------------


async def _run_extraction(project_id: str, pptx_path: str) -> None:
    """Run Agent 0 PPTX extraction in background."""
    try:
        from agents.agent0_pptx_parser import PPTXParserAgent

        logger.info("Starting extraction for project %s from %s", project_id, pptx_path)
        agent = PPTXParserAgent()
        result = await agent.parse(pptx_path, project_id)
        logger.info("Extraction returned %d rooms for project %s", len(result.rooms), project_id)

        # Convert to V5 models
        v5_rooms = []
        for room_data in result.rooms:
            products = [
                Product(
                    id=p["id"],
                    name=p.get("name", "Unknown"),
                    dimensions=p.get("dimensions") or "",
                    image_path=p.get("image_path") or "",
                    room_id=room_data["id"],
                    slide_index=p.get("slide_index"),
                )
                for p in room_data.get("products", [])
            ]
            v5_rooms.append(V5Room(
                id=room_data["id"],
                label=room_data["label"],
                floor=room_data.get("floor", "ground"),
                status="extracted",
                layout_image_path=room_data.get("layout_image_path", ""),
                products=products,
            ))

        floor_plans = [
            FloorPlan(
                id=fp["id"],
                floor_name=fp.get("floor_name", "ground"),
                image_path=fp.get("image_path", ""),
            )
            for fp in result.floor_plans
        ]

        await _state.update_project(project_id, {
            "v5_rooms": [r.model_dump() for r in v5_rooms],
            "floor_plans": [fp.model_dump() for fp in floor_plans],
            "status": "reviewing_extraction",
        })

        logger.info(
            "Extraction complete for project %s: %d rooms, %d floor plans",
            project_id, len(v5_rooms), len(floor_plans),
        )

    except Exception as exc:
        logger.exception("Extraction failed for project %s: %s", project_id, exc)
        await _state.update_project(project_id, {"status": "failed"})


async def _run_image_generation(project_id: str) -> None:
    """Run Agent 2.5 image generation for all approved rooms."""
    try:
        project = await _state.get_project(project_id)

        # Load floor plan image if available
        floor_plan_bytes: bytes | None = None
        if project.floor_plans:
            fp_path = Path(project.floor_plans[0].image_path)
            if fp_path.exists():
                floor_plan_bytes = fp_path.read_bytes()

        from agents.agent2_5_composer import SceneComposerAgent

        composer = SceneComposerAgent()

        # Collect room IDs upfront to avoid mutating the loop target
        room_ids_to_process = [r.id for r in project.v5_rooms if r.status == "approved"]

        for room_id in room_ids_to_process:
            # Reload fresh state before each room to avoid race conditions
            project = await _state.get_project(project_id)
            room = next((r for r in project.v5_rooms if r.id == room_id), None)
            if room is None or room.status != "approved":
                continue

            room.status = "generating"
            await _state.update_project(project_id, {
                "v5_rooms": [r.model_dump() for r in project.v5_rooms],
            })

            try:
                await _generate_room_images(
                    project_id, room, composer, floor_plan_bytes
                )
            except Exception as exc:
                logger.exception("Image gen failed for room %s: %s", room.id, exc)
                # Reload and reset to allow retry
                project = await _state.get_project(project_id)
                failed_room = next((r for r in project.v5_rooms if r.id == room_id), None)
                if failed_room:
                    failed_room.status = "generation_failed"
                    await _state.update_project(project_id, {
                        "v5_rooms": [r.model_dump() for r in project.v5_rooms],
                    })

        # Reload and update status
        project = await _state.get_project(project_id)
        all_ready = all(
            r.status in ("image_ready", "image_approved")
            for r in project.v5_rooms
        )
        if all_ready:
            await _state.update_project(project_id, {"status": "reviewing_images"})

    except Exception:
        logger.exception("Image generation pipeline failed for project %s", project_id)
        await _state.update_project(project_id, {"status": "failed"})


async def _generate_room_images(
    project_id: str,
    room: V5Room,
    composer,
    floor_plan_bytes: bytes | None,
) -> None:
    """Generate images for a single room using Agent 2.5."""
    # Load product images
    furniture_images: list[bytes] = []
    for prod in room.products:
        if prod.image_path and Path(prod.image_path).exists():
            furniture_images.append(Path(prod.image_path).read_bytes())

    if not floor_plan_bytes and not furniture_images:
        logger.warning("No images available for room %s, skipping", room.id)
        return

    composed = await composer.compose(
        room_id=room.id,
        room_label=room.label,
        floor_plan_bytes=floor_plan_bytes or b"",
        furniture_images=furniture_images,
    )

    # Save images
    output_dir = TEMP_DIR / "storage" / f"projects/{project_id}/rooms/{room.id}/images"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save base render
    base_id = str(uuid.uuid4())[:8]
    base_path = output_dir / f"base_{base_id}.png"
    base_path.write_bytes(composed.base_render)

    # Save refined render
    refined_id = str(uuid.uuid4())[:8]
    refined_path = output_dir / f"refined_{refined_id}.png"
    refined_path.write_bytes(composed.refined_render)

    room.generated_images = [
        GeneratedImage(
            id=base_id,
            room_id=room.id,
            image_path=str(base_path),
            prompt_used=composed.description[:500],
            version=1,
            type="base",
        ),
        GeneratedImage(
            id=refined_id,
            room_id=room.id,
            image_path=str(refined_path),
            prompt_used=composed.description[:500],
            version=2,
            type="refined",
        ),
    ]
    room.status = "image_ready"

    # Persist — use module-level _state, not a new instance
    project = await _state.get_project(project_id)
    for r in project.v5_rooms:
        if r.id == room.id:
            r.generated_images = room.generated_images
            r.status = room.status
            break
    await _state.update_project(project_id, {
        "v5_rooms": [r.model_dump() for r in project.v5_rooms],
    })

    logger.info("Images generated for room %s: base=%s, refined=%s", room.id, base_id, refined_id)


async def _run_single_room_generation(project_id: str, room_id: str) -> None:
    """Regenerate images for a single room."""
    try:
        project = await _state.get_project(project_id)
        room = next((r for r in project.v5_rooms if r.id == room_id), None)
        if room is None:
            return

        floor_plan_bytes: bytes | None = None
        if project.floor_plans:
            fp_path = Path(project.floor_plans[0].image_path)
            if fp_path.exists():
                floor_plan_bytes = fp_path.read_bytes()

        from agents.agent2_5_composer import SceneComposerAgent

        composer = SceneComposerAgent()
        await _generate_room_images(project_id, room, composer, floor_plan_bytes)

    except Exception:
        logger.exception("Single room regeneration failed: %s/%s", project_id, room_id)


# ---------------------------------------------------------------------------
# Video prompt builder — varied camera angles per room type
# ---------------------------------------------------------------------------
# Research: Kling image-to-video best practices (2026):
#   - ONE clear camera movement per prompt (no contradictions)
#   - Structure: Shot type + camera motion + environment + constraints
#   - Match movement to space: dolly/tracking for tight interiors,
#     orbit/crane for large open spaces
#   - cfg_scale 0.3-0.5 for natural architectural motion
#   - Never redescribe the image — only specify motion
# Sources:
#   - https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide
#   - https://www.ambienceai.com/tutorials/kling-prompting-guide
#   - https://blog.segmind.com/cinematic-ai-camera-movements-in-kling-ai-1-6-top-7-types/

_CAMERA_MOVES = {
    # Room keywords → (camera move, extra environment notes)
    "reception": ("Smooth steadicam tracking shot moving forward through the reception area, camera at eye level, gliding past the front desk", "warm ambient lighting, corporate elegance"),
    "accueil": ("Smooth steadicam tracking shot moving forward through the reception area, camera at eye level, gliding past the front desk", "warm ambient lighting, corporate elegance"),
    "lounge": ("Gentle dolly-in towards the seating area, camera slowly panning right to reveal the full lounge layout", "soft diffused lighting, relaxed atmosphere"),
    "conversation": ("Camera slowly orbits around the conversation seating from left to right, maintaining medium distance", "intimate lighting, professional setting"),
    "negotiation": ("Slow dolly forward into the negotiation area, camera tilting slightly down to showcase the table setup", "focused task lighting, business atmosphere"),
    "kids": ("Playful tracking shot sweeping left across the kids zone, camera at child height rising slightly", "bright colorful lighting, energetic space"),
    "escape": ("Playful tracking shot sweeping left across the play area, camera at child height rising slightly", "bright colorful lighting, energetic space"),
    "magasin": ("Wide tracking shot moving right through the showroom floor, camera panning to follow product displays", "even retail lighting, spacious commercial feel"),
    "shop": ("Wide tracking shot moving right through the showroom floor, camera panning to follow product displays", "even retail lighting, spacious commercial feel"),
    "office": ("Slow dolly-in through the office space, camera at desk height, subtle pan left to reveal workstations", "clean natural window light, productive atmosphere"),
    "gm": ("Elegant push-in towards the executive desk, camera rising slightly for a commanding perspective", "warm directional lighting, executive prestige"),
    "manager": ("Elegant push-in towards the executive desk, camera rising slightly for a commanding perspective", "warm directional lighting, executive prestige"),
    "conference": ("Slow crane-down from above revealing the conference table, settling at seated eye level", "overhead panel lighting, formal meeting space"),
    "training": ("Slow crane-down from above revealing the conference table, settling at seated eye level", "overhead panel lighting, formal meeting space"),
    "cashier": ("Compact dolly-right past the cashier counter, camera maintaining focus on the service area", "functional task lighting, efficient workspace"),
    "maintenance": ("Steady tracking shot forward through the maintenance reception, camera at standing height", "practical even lighting, service-oriented space"),
    "customer": ("Gentle arc orbit around the lounge seating, camera moving from left to right at seated height", "warm relaxed lighting, comfortable waiting area"),
}

_DEFAULT_MOVE = ("Smooth cinematic tracking shot moving forward through the room, camera at eye level with gentle rightward pan", "natural ambient lighting, architectural interior")


def _build_video_prompt(room_label: str, products: list | None = None) -> str:
    """Build a room-specific video prompt with varied camera angles."""
    label_lower = room_label.lower()

    # Find best matching camera move
    camera_move, env_note = _DEFAULT_MOVE
    for keyword, (move, env) in _CAMERA_MOVES.items():
        if keyword in label_lower:
            camera_move, env_note = move, env
            break

    # Build the prompt — motion-only (never redescribe the image)
    prompt = (
        f"{camera_move}. "
        f"{env_note.capitalize()}, photorealistic interior design visualization, "
        f"smooth gimbal-stabilized movement, no camera shake. "
        f"No people, no text overlays, no sudden transitions."
    )
    return prompt


async def _run_video_generation(project_id: str, video_mode: str = "standard") -> None:
    """Generate videos for all approved rooms. mode: standard (MiniMax) or premium (Kling)."""
    try:
        project = await _state.get_project(project_id)
        approved_rooms = [r for r in project.v5_rooms if r.status == "image_approved"]

        from services.fal_video import FalVideoService

        fal = FalVideoService()

        for room in approved_rooms:
            if not room.generated_images:
                continue

            # Use the latest/best image as the video start frame
            best_image = room.generated_images[-1]
            frame_path = Path(best_image.image_path)
            if not frame_path.exists():
                continue

            frame_bytes = frame_path.read_bytes()
            prompt = _build_video_prompt(room.label, room.products)

            # Retry up to 2 times with backoff
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    video_bytes = await fal.generate_video(
                        start_frame_bytes=frame_bytes,
                        prompt=prompt,
                        max_duration_seconds=5,
                        cfg_scale=0.4,
                        video_mode=video_mode,
                    )

                    # Save video
                    video_dir = TEMP_DIR / "storage" / f"projects/{project_id}/rooms/{room.id}/video"
                    video_dir.mkdir(parents=True, exist_ok=True)
                    video_path = video_dir / "room.mp4"
                    video_path.write_bytes(video_bytes)

                    room.video_path = str(video_path)
                    room.status = "video_ready"

                    logger.info("Video generated for room %s: %d bytes", room.id, len(video_bytes))
                    break  # success

                except Exception as exc:
                    if attempt < max_retries:
                        wait = 10 * (attempt + 1)
                        logger.warning(
                            "Video gen attempt %d/%d failed for room %s, retrying in %ds: %s",
                            attempt + 1, max_retries + 1, room.id, wait, exc,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.exception("Video gen failed for room %s after %d attempts: %s", room.id, max_retries + 1, exc)
                        room.status = "video_failed"

            # Persist after EACH room so progress survives crashes
            await _state.update_project(project_id, {
                "v5_rooms": [r.model_dump() for r in project.v5_rooms],
            })

        # Check if all rooms that should have video actually do
        rooms_needing_video = [
            r for r in project.v5_rooms
            if r.status in ("image_approved", "video_ready")
        ]
        all_ready = bool(rooms_needing_video) and all(r.video_path for r in rooms_needing_video)
        if all_ready:
            logger.info("All videos ready for project %s", project_id)

    except Exception:
        logger.exception("Video generation failed for project %s", project_id)
        await _state.update_project(project_id, {"status": "failed"})
