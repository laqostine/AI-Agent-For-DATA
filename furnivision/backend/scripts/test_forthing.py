"""
FurniVision — Forthing Project End-to-End Test

Runs Agents 2.5 → 2 → 3 → 4 → 5 for selected rooms using:
  - Floor plan PDFs (GROUND FLOOR + MEZZANINE)
  - Furniture catalogue images from the Forthing folder

Output images are saved and opened for inspection at every stage.

Usage:
    cd /Users/bera/Documents/GitHub/AI-Agent-For-DATA/furnivision/backend
    python scripts/test_forthing.py
"""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_forthing")

# ── Asset paths ───────────────────────────────────────────────────────────────
FORTHING_DIR = Path(
    "/Users/bera/Library/Containers/net.whatsapp.WhatsApp/Data"
    "/tmp/documents/1E5426B3-58F1-48F5-A7A0-76C4064A3E43/Forthing"
)
GF_PDF   = Path("/Users/bera/Downloads/GROUND FLOOR (1).pdf")
MEZ_PDF  = Path("/Users/bera/Downloads/MEZZANNINE.pdf")
OUT_DIR  = Path("/tmp/furnivision/forthing_output")

# ── Room definitions ──────────────────────────────────────────────────────────
# Each entry: (room_label, floor_plan_pdf, forthing_subfolder, furniture_spec)
# furniture_spec: list of (item_name, item_type, color_primary, material)
ROOMS = [
    {
        "label": "Conversation area",
        "floor_pdf": GF_PDF,
        "img_dir": FORTHING_DIR / "GROUND FLOOR" / "Conversation area",
        "furniture": [
            ("terracotta boucle armchair", "chair",  "terracotta", "boucle fabric"),
            ("round coffee table",         "table",  "white",      "laminate"),
            ("modular shelving unit",      "shelf",  "beige",      "metal and wood"),
        ],
        "brief": {
            "ceiling_height_m": 3.5,
            "floor_material":   "light oak parquet",
            "wall_color":       "warm white",
            "overall_style":    "modern commercial showroom",
            "lighting_mood":    "bright natural daylight with warm accent lighting",
        },
        "room_polygon": [[0.05, 0.55], [0.95, 0.55], [0.95, 0.95], [0.05, 0.95]],
        "area_sqm": 80.0,
    },
    {
        "label": "General manager office",
        "floor_pdf": MEZ_PDF,
        "img_dir": FORTHING_DIR / "MEZZANNINE" / "General manager office",
        "furniture": [
            ("executive office chair",    "chair",  "black",   "mesh and plastic"),
            ("executive desk",            "desk",   "white",   "laminate"),
            ("meeting table",             "table",  "white",   "laminate"),
            ("visitor chair",             "chair",  "terracotta", "fabric"),
        ],
        "brief": {
            "ceiling_height_m": 2.8,
            "floor_material":   "polished concrete",
            "wall_color":       "light grey",
            "overall_style":    "modern executive office",
            "lighting_mood":    "professional daylight with recessed LED lighting",
        },
        "room_polygon": [[0.05, 0.65], [0.45, 0.65], [0.45, 0.95], [0.05, 0.95]],
        "area_sqm": 35.0,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def open_file(path: str | Path) -> None:
    """Open a file with the default macOS viewer."""
    subprocess.run(["open", str(path)], check=False)


def open_folder(path: str | Path) -> None:
    """Open a folder in Finder."""
    subprocess.run(["open", str(path)], check=False)


def load_images_from_dir(img_dir: Path) -> list[bytes]:
    """Load all PNG/JPG images from a directory, largest files first."""
    if not img_dir.exists():
        logger.warning("Image dir not found: %s", img_dir)
        return []
    files = [
        f for f in img_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg")
        and not f.name.startswith(".")
    ]
    # Sort by size descending (largest = highest quality)
    files.sort(key=lambda f: f.stat().st_size, reverse=True)
    images = []
    for f in files:
        data = f.read_bytes()
        images.append(data)
        logger.info("  Loaded furniture image: %s (%d KB)", f.name, len(data) // 1024)
    return images


def pdf_to_png_bytes(pdf_path: Path, dpi: int = 150) -> bytes:
    """Convert first page of a PDF to PNG bytes using PyMuPDF."""
    import fitz
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    logger.info(
        "Floor plan PDF → PNG: %s (%d KB, %dx%d px)",
        pdf_path.name, len(png_bytes) // 1024, pix.width, pix.height,
    )
    return png_bytes


def make_furniture_items(specs: list[tuple]) -> list:
    """Build FurnitureItem model instances from the spec list."""
    from models.project import FurnitureItem
    items = []
    for i, (name, itype, color, material) in enumerate(specs):
        items.append(FurnitureItem(
            id=f"fi_{i:02d}_{itype}",
            furniture_image_index=i,
            item_name=name,
            item_type=itype,
            color_primary=color,
            material=material,
            style_tags=["modern", "commercial"],
            image_quality="product_render",
        ))
    return items


def make_room(room_cfg: dict, furniture_items: list) -> object:
    """Build a RoomGeometry model from config."""
    from models.project import RoomGeometry
    return RoomGeometry(
        id=f"room_{room_cfg['label'].lower().replace(' ', '_')[:20]}",
        label=room_cfg["label"],
        polygon_relative=room_cfg["room_polygon"],
        area_sqm_estimated=room_cfg["area_sqm"],
        position_on_plan=f"extracted from floor plan",
        furniture_items=furniture_items,
    )


def make_brief(brief_cfg: dict) -> object:
    """Build a ProjectBrief from config."""
    from models.project import ProjectBrief
    return ProjectBrief(**brief_cfg)


def save_image(data: bytes, path: Path, label: str) -> None:
    """Save image bytes to disk and log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.info("  ✓ Saved %s → %s (%d KB)", label, path.name, len(data) // 1024)


# ── Per-stage runners ─────────────────────────────────────────────────────────

async def run_step_composer(
    room_cfg: dict,
    floor_plan_bytes: bytes,
    furniture_images: list[bytes],
    room_out: Path,
) -> "ComposedScene":
    from agents.agent2_5_composer import SceneComposerAgent
    room_id = f"room_{room_cfg['label'].lower().replace(' ', '_')[:20]}"

    print(f"\n{'='*60}")
    print(f"STEP 1 — Agent 2.5: Scene Composer  [{room_cfg['label']}]")
    print(f"{'='*60}")
    print(f"  Floor plan PNG: {len(floor_plan_bytes)//1024} KB")
    print(f"  Furniture images: {len(furniture_images)}")
    print("  → Asking Gemini to analyse floor plan + all furniture images...")
    print("  → Then generating reference render with Imagen 4...")

    agent = SceneComposerAgent()
    composed = await agent.compose(
        room_id=room_id,
        room_label=room_cfg["label"],
        floor_plan_bytes=floor_plan_bytes,
        furniture_images=furniture_images,
    )

    # Save outputs
    desc_path = room_out / "step1_gemini_description.txt"
    desc_path.write_text(composed.description, encoding="utf-8")
    logger.info("  Description saved: %s", desc_path.name)

    render_path = room_out / "step1_composed_render.png"
    save_image(composed.reference_render, render_path, "Composed reference render")

    print(f"\n  ✓ Gemini description ({len(composed.description)} chars):")
    print(f"    {composed.description[:300]}...")
    print(f"\n  ✓ Imagen reference render: {len(composed.reference_render)//1024} KB")
    print(f"  → Opening render...")
    open_file(render_path)

    return composed


async def run_step_planner(
    room_cfg: dict,
    project_id: str,
    room_out: Path,
) -> "ScenePlan":
    from agents.agent2_planner import PlannerAgent
    from models.project import FurnitureItem

    print(f"\n{'='*60}")
    print(f"STEP 2 — Agent 2: Scene Planner  [{room_cfg['label']}]")
    print(f"{'='*60}")

    furniture_items = make_furniture_items(
        [(n, t, c, m) for n, t, c, m in [
            (spec[0], spec[1], spec[2], spec[3])
            for spec in room_cfg["furniture"]
        ]]
    )
    room = make_room(room_cfg, furniture_items)
    brief = make_brief(room_cfg["brief"])

    agent = PlannerAgent()
    scene_plan = await agent.plan(
        room=room,
        furniture_items=furniture_items,
        brief=brief,
        project_style=room_cfg["brief"]["overall_style"],
        project_id=project_id,
    )

    plan_path = room_out / "step2_scene_plan.txt"
    plan_text = (
        f"Room: {scene_plan.room.label}\n"
        f"Style anchor: {scene_plan.style_anchor}\n\n"
        f"Camera positions ({len(scene_plan.camera_positions)}):\n"
        + "\n".join(
            f"  [{i}] h={c.height_m}m fov={c.fov_deg}° → {c.look_at_description}"
            for i, c in enumerate(scene_plan.camera_positions)
        )
        + f"\n\nFurniture layout ({len(scene_plan.furniture_layout)} items):\n"
        + "\n".join(
            f"  {fi['item_id']} at ({fi['x_m']:.2f}, {fi['y_m']:.2f}) rot={fi['rotation_deg']:.0f}°"
            for fi in scene_plan.furniture_layout
        )
        + f"\n\nFirst keyframe prompt:\n{scene_plan.prompts[0][:500]}..."
    )
    plan_path.write_text(plan_text, encoding="utf-8")

    print(f"  ✓ Scene plan: {len(scene_plan.camera_positions)} cameras, {len(scene_plan.prompts)} prompts")
    print(f"  ✓ Furniture layout: {len(scene_plan.furniture_layout)} items placed")
    print(f"  Style: {scene_plan.style_anchor[:100]}...")

    return scene_plan, room


async def run_step_generator(
    room_cfg: dict,
    project_id: str,
    room_id: str,
    scene_plan,
    composed_reference: bytes,
    room_out: Path,
) -> list:
    from agents.agent3_generator import GeneratorAgent

    print(f"\n{'='*60}")
    print(f"STEP 3 — Agent 3: Image Generator  [{room_cfg['label']}]")
    print(f"{'='*60}")
    print("  Using composed render as reference → Gemini Flash Image img2img")
    print("  Generating 2 keyframes...")

    agent = GeneratorAgent()
    frame_statuses = await agent.generate_all_frames(
        scene_plan=scene_plan,
        project_id=project_id,
        room_id=room_id,
        job_id=str(uuid.uuid4()),
        reference_images=[composed_reference],
    )

    print(f"\n  Results:")
    for fs in frame_statuses:
        status_icon = "✓" if fs.status == "complete" else "✗"
        print(f"  {status_icon} Frame {fs.frame_idx}: {fs.status} → {fs.gcs_url or 'no path'}")

    # Download and save the generated frames for viewing
    from services.storage import StorageService
    storage = StorageService()
    frame_images = []
    for fs in frame_statuses:
        if fs.status == "complete" and fs.gcs_url:
            try:
                img_bytes = await storage.download_bytes(fs.gcs_url)
                frame_path = room_out / f"step3_keyframe_{fs.frame_idx}.png"
                save_image(img_bytes, frame_path, f"Keyframe {fs.frame_idx}")
                frame_images.append((fs.frame_idx, frame_path, img_bytes))
                print(f"  → Opening keyframe {fs.frame_idx}...")
                open_file(frame_path)
            except Exception as e:
                logger.warning("Could not download frame %d: %s", fs.frame_idx, e)

    return frame_statuses


async def run_step_validator(
    room_cfg: dict,
    frame_statuses: list,
    scene_plan,
    room_id: str,
    room_out: Path,
) -> object:
    from agents.agent4_validator import ValidatorAgent

    print(f"\n{'='*60}")
    print(f"STEP 4 — Agent 4: QC Validator  [{room_cfg['label']}]")
    print(f"{'='*60}")
    print("  Running histogram matching + Gemini pairwise consistency check...")

    agent = ValidatorAgent()
    validation = await agent.validate(
        frames=frame_statuses,
        scene_plan=scene_plan,
        room_id=room_id,
    )

    score = getattr(validation, "overall_score", getattr(validation, "consistency_score", None))
    hero_urls = getattr(validation, "graded_frame_urls", [])
    print(f"\n  ✓ QC score: {score:.2f}" if score is not None else "  ✓ QC complete")
    print(f"  ✓ Graded frame URLs: {len(hero_urls)}")

    # Download and open validated frames
    from services.storage import StorageService
    storage = StorageService()
    for i, url in enumerate(hero_urls[:2]):
        if url:
            try:
                # Strip local URL prefix if present
                gcs_path = url.removeprefix("/api/v1/local-storage/")
                img_bytes = await storage.download_bytes(gcs_path)
                v_path = room_out / f"step4_validated_{i}.png"
                save_image(img_bytes, v_path, f"Validated frame {i}")
                print(f"  → Opening validated frame {i}...")
                open_file(v_path)
            except Exception as e:
                logger.warning("Could not download validated frame %d: %s", i, e)

    return validation


async def run_step_animator(
    room_cfg: dict,
    project_id: str,
    room_id: str,
    frame_statuses: list,
    scene_plan,
    composed_reference: bytes,
    room_out: Path,
) -> object:
    from agents.agent5_animator import AnimatorAgent

    print(f"\n{'='*60}")
    print(f"STEP 5 — Agent 5: Animator (Veo 3)  [{room_cfg['label']}]")
    print(f"{'='*60}")
    print("  Using composed reference render as Veo 3 starting frame...")
    print("  Generating 8-second cinematic walkthrough...")

    agent = AnimatorAgent()
    result = await agent.animate(
        validated_frames=frame_statuses,
        scene_plan=scene_plan,
        project_id=project_id,
        room_id=room_id,
        reference_images=[composed_reference],
    )

    print(f"\n  ✓ Video URL: {result.video_url[:80]}...")
    print(f"  ✓ Viewer manifest: {result.viewer_manifest_url[:80]}...")

    # Download and save video
    from services.storage import StorageService
    storage = StorageService()
    try:
        gcs_path = result.video_url.removeprefix("/api/v1/local-storage/")
        video_bytes = await storage.download_bytes(gcs_path)
        video_path = room_out / "step5_walkthrough.mp4"
        video_path.write_bytes(video_bytes)
        logger.info("  ✓ Video saved: %s (%d KB)", video_path.name, len(video_bytes) // 1024)
        print(f"  → Opening video...")
        open_file(video_path)
    except Exception as e:
        logger.warning("Could not save video via storage: %s", e)
        # Direct fallback: video was also saved to TEMP_DIR by Veo service
        import glob as _glob
        mp4_hits = _glob.glob(f"/tmp/furnivision/**/*.mp4", recursive=True)
        if mp4_hits:
            # pick the most recently modified
            mp4_hits.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
            video_path = room_out / "step5_walkthrough.mp4"
            video_path.write_bytes(Path(mp4_hits[0]).read_bytes())
            logger.info("  ✓ Video copied from temp: %s", mp4_hits[0])
            open_file(video_path)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_room(room_cfg: dict) -> None:
    """Run the full Agent 2.5 → 2 → 3 → 4 → 5 pipeline for one room."""
    label = room_cfg["label"]
    project_id = f"forthing_{label.lower().replace(' ', '_')[:20]}_{uuid.uuid4().hex[:6]}"
    room_id = f"room_{label.lower().replace(' ', '_')[:20]}"
    room_out = OUT_DIR / label.replace(" ", "_")
    room_out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'#'*65}")
    print(f"  ROOM: {label}")
    print(f"  Project ID: {project_id}")
    print(f"  Output: {room_out}")
    print(f"{'#'*65}")

    # Load assets
    print("\n[Loading assets]")
    floor_plan_bytes = pdf_to_png_bytes(room_cfg["floor_pdf"])
    # Save floor plan image for reference
    fp_path = room_out / "floor_plan.png"
    fp_path.write_bytes(floor_plan_bytes)
    logger.info("  Floor plan image saved: %s", fp_path.name)

    print(f"  Loading furniture images from: {room_cfg['img_dir'].name}")
    furniture_images = load_images_from_dir(room_cfg["img_dir"])
    if not furniture_images:
        logger.error("  No furniture images found! Check path: %s", room_cfg["img_dir"])
        return
    print(f"  Loaded {len(furniture_images)} furniture images")

    # STEP 1: SceneComposer
    composed = await run_step_composer(room_cfg, floor_plan_bytes, furniture_images, room_out)

    # STEP 2: Planner
    scene_plan, room_model = await run_step_planner(room_cfg, project_id, room_out)

    # STEP 3: Generator (using composed render as reference)
    frame_statuses = await run_step_generator(
        room_cfg, project_id, room_id, scene_plan,
        composed.reference_render, room_out,
    )

    completed_frames = [fs for fs in frame_statuses if fs.status == "complete"]
    if not completed_frames:
        print("\n  ⚠ No frames generated successfully — skipping Validator and Animator")
        return

    # STEP 4: Validator
    validation = await run_step_validator(
        room_cfg, frame_statuses, scene_plan, room_id, room_out
    )

    # STEP 5: Animator
    animation = await run_step_animator(
        room_cfg, project_id, room_id, frame_statuses,
        scene_plan, composed.reference_render, room_out,
    )

    print(f"\n{'='*60}")
    print(f"  COMPLETE: {label}")
    print(f"  All outputs in: {room_out}")
    print(f"{'='*60}")


async def concat_room_videos(rooms: list[dict]) -> None:
    """Concatenate all room videos into a single master video using ffmpeg."""
    print(f"\n{'='*60}")
    print("FINAL — Concatenating all room videos")
    print(f"{'='*60}")

    # Collect existing video files in room order
    video_paths = []
    for room_cfg in rooms:
        label = room_cfg["label"]
        v = OUT_DIR / label.replace(" ", "_") / "step5_walkthrough.mp4"
        if v.exists():
            video_paths.append((label, v))
            print(f"  + {label}: {v.name} ({v.stat().st_size // 1024} KB)")
        else:
            print(f"  - {label}: video not found, skipping")

    if len(video_paths) < 2:
        print("  ⚠ Need at least 2 videos to concatenate — skipping")
        return

    master_path = OUT_DIR / "FORTHING_all_rooms.mp4"

    # Write ffmpeg concat list
    concat_list = OUT_DIR / "_concat_list.txt"
    concat_list.write_text(
        "\n".join(f"file '{p}'" for _, p in video_paths),
        encoding="utf-8",
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(master_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        size_mb = master_path.stat().st_size / (1024 * 1024)
        print(f"\n  ✓ Master video: {master_path}")
        print(f"    {len(video_paths)} rooms, {size_mb:.1f} MB total")
        print("  → Opening master video...")
        open_file(master_path)
    else:
        print(f"  ✗ ffmpeg failed: {result.stderr[-300:]}")

    concat_list.unlink(missing_ok=True)


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  FurniVision — Forthing Project Pipeline Test            ║")
    print("║  Agents: 2.5 (Compose) → 2 (Plan) → 3 (Gen)            ║")
    print("║           → 4 (Validate) → 5 (Animate)                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\nOutput directory: {OUT_DIR}")
    print(f"Rooms to process: {[r['label'] for r in ROOMS]}\n")

    for room_cfg in ROOMS:
        try:
            await run_room(room_cfg)
        except Exception as e:
            logger.exception("Room '%s' failed: %s", room_cfg["label"], e)
            print(f"\n  ✗ Room '{room_cfg['label']}' failed: {e}")
            print("  Continuing with next room...\n")

    # Concatenate all room videos into one master video
    await concat_room_videos(ROOMS)

    print(f"\n{'#'*65}")
    print("  ALL ROOMS COMPLETE")
    print(f"  Opening output folder: {OUT_DIR}")
    print(f"{'#'*65}\n")
    open_folder(OUT_DIR)


if __name__ == "__main__":
    asyncio.run(main())
