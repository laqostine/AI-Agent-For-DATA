# FurniVision V5 — Human-in-the-Loop System

## What it does
Takes a furniture spec PPTX/PDF (like FORTHING SHOWROOM.pptx) → extracts rooms + products → generates room visualizations → creates walkthrough video. Human reviews and gives feedback at every step.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND                             │
│  Upload → Extraction Review → Image Review → Video → Download     │
└──────────┬───────────────────────────────────────────┬───────────┘
           │                                           │
           ▼                                           ▼
┌──────────────────────┐                    ┌─────────────────────┐
│     FastAPI Backend   │                    │   Background Workers │
│  /upload-spec         │                    │   Agent 0: PPTX Parse│
│  /extraction          │◄──────────────────►│   Agent 2.5: Compose │
│  /rooms/{id}/approve  │                    │   Agent 3: Generate  │
│  /rooms/{id}/feedback │                    │   Agent 5: Video     │
│  /compile             │                    │   Compiler: ffmpeg   │
└──────────────────────┘                    └─────────────────────┘
           │
           ▼
┌──────────────────────┐
│   State + Storage     │
│  Firestore / Memory   │
│  GCS / Local files    │
└──────────────────────┘
```

## 4 Stages

### Stage 0: Upload & Extract
- **Input:** Client uploads PPTX (or PDF)
- **AI:** New Agent 0 (PPTX Parser) extracts:
  - Floor plan images (from overview slides)
  - Per-room: layout diagram + product images + labels + dimensions
  - Auto-maps products to rooms based on slide structure
- **Output:** JSON with rooms[], each with products[]

### Stage 1: Human Gate — Review Extraction
- **Frontend:** Shows each room with its assigned products
- **Human can:** Rename rooms, reassign products, swap product images, remove/add items
- **On approve:** Triggers image generation

### Stage 2: Generate Room Images
- **AI Pipeline per room:**
  1. Imagen 4 → 16:9 base render (1536x864) with room description
  2. Gemini Flash Image → refine with product images as inline_data refs (3 attempts, best pick)
  3. Structured JSON prompt with exact product specs
- **Output:** keyframe_0.png per room

### Stage 3: Human Gate — Review Images
- **Frontend:** Side-by-side comparison (real products vs AI generated) per room
- **Human can:**
  - Approve room ✓
  - Give text feedback ("chairs need casters", "wrong color") → AI re-edits using Gemini Flash Image edit
  - Swap a product image → re-generates just that room
  - Re-generate from scratch → runs Stage 2 again for that room
- **Loop** until all rooms approved

### Stage 4: Video & Deliver
- **AI:** Kling (fal.ai) generates 7s video per approved room
- **Compile:** ffmpeg concats all + ambient music + logo end card
- **Scale:** ffmpeg to 1920x1080
- **Output:** Final MP4

## Data Model

```python
class Project:
    id: str
    name: str
    status: "uploading" | "extracting" | "reviewing_extraction" | "generating_images" | "reviewing_images" | "generating_videos" | "complete"
    spec_file_path: str
    floor_plans: list[FloorPlan]
    rooms: list[Room]
    logo_path: str | None
    music_path: str | None
    final_video_path: str | None

class FloorPlan:
    id: str
    floor_name: str  # "ground" | "mezzanine"
    image_path: str

class Room:
    id: str
    label: str
    floor: str
    status: "pending" | "extracted" | "approved" | "generating" | "image_ready" | "image_approved" | "video_ready" | "complete"
    layout_image_path: str
    products: list[Product]
    generated_images: list[GeneratedImage]
    video_path: str | None
    feedback: list[str]

class Product:
    id: str
    name: str
    dimensions: str
    image_path: str  # clean product render
    room_id: str

class GeneratedImage:
    id: str
    room_id: str
    image_path: str
    prompt_used: str
    version: int
    type: "base" | "refined" | "edited"
```

## API Endpoints

```
# Project
POST   /api/projects                        → Create project
POST   /api/projects/{id}/upload-spec       → Upload PPTX/PDF
GET    /api/projects/{id}                   → Get project status

# Extraction
POST   /api/projects/{id}/extract           → Trigger AI extraction (async)
GET    /api/projects/{id}/extraction         → Get extraction results

# Gate 1: Review extraction
PUT    /api/projects/{id}/rooms/{rid}        → Edit room (name, products)
POST   /api/projects/{id}/rooms/{rid}/swap-product → Swap product image
POST   /api/projects/{id}/approve-extraction → Approve all → trigger image gen

# Image generation
GET    /api/projects/{id}/rooms/{rid}/images → Get generated images
POST   /api/projects/{id}/rooms/{rid}/regenerate → Re-generate room images

# Gate 2: Review images
POST   /api/projects/{id}/rooms/{rid}/feedback  → Text feedback → AI edit
POST   /api/projects/{id}/rooms/{rid}/approve   → Approve room image

# Video & compile
POST   /api/projects/{id}/generate-videos    → Generate all approved room videos
POST   /api/projects/{id}/compile            → Compile final video
GET    /api/projects/{id}/final-video        → Download final MP4

# Assets
POST   /api/projects/{id}/upload-logo       → Upload company logo
POST   /api/projects/{id}/upload-music       → Upload background music
```

## Frontend Pages

### 1. Upload Page
- Drag & drop PPTX/PDF
- Optional: logo, music file
- "Extract" button → shows loading

### 2. Extraction Review (Gate 1)
- Left: floor plan with room zones highlighted
- Right: card per room showing:
  - Room name (editable)
  - Product images grid (can remove/swap)
  - "Approve" or "Edit" per room
- "Approve All" button at bottom

### 3. Image Review (Gate 2)
- Per room card:
  - Left: real product images from PPTX
  - Right: AI generated room render
  - Below: text feedback input + "Re-edit" button
  - "Approve" checkmark
- Progress bar showing rooms approved

### 4. Video Preview
- Play all room videos in sequence
- Individual room video player
- "Regenerate" per room if needed
- "Compile Final" button

### 5. Download
- Final video player
- Download MP4 button
- Share link

## What Exists vs What to Build

### EXISTS (from current codebase):
- FastAPI backend with routes ✅
- Agent pipeline (1-5) ✅
- Human gates with polling ✅
- State management ✅
- Storage service ✅
- Gemini / Imagen / Kling services ✅
- Fal.ai video service ✅
- PDF processor ✅
- React frontend (basic) ✅
- V4 image pipeline (Imagen base → Gemini refine) ✅
- Video compilation with ffmpeg ✅

### TO BUILD:
1. **Agent 0: PPTX Parser** — Extract slides, images, labels per room
   - Uses python-pptx to extract clean product images
   - Uses Gemini to understand slide structure and map products to rooms
   - Files: `backend/agents/agent0_pptx_parser.py`

2. **Update Agent 2.5: SceneComposer** — V4 pipeline
   - Imagen 4 → 16:9 base render
   - Gemini Flash Image → multi-ref refinement (3 attempts, best pick)
   - Structured JSON prompts
   - Files: `backend/agents/agent2_5_composer.py` (update)

3. **New: Image Edit endpoint** — Targeted edits from feedback
   - Takes existing image + feedback text + product ref image
   - Gemini Flash Image edits specific elements
   - Files: `backend/api/routes/edit.py`

4. **New: Video Compiler service** — Final video assembly
   - Concat room videos + music + logo end card
   - ffmpeg pipeline
   - Files: `backend/services/video_compiler.py`

5. **Frontend: Extraction Review page** — Gate 1 UI
   - Files: `frontend/src/pages/ExtractionReview.tsx`

6. **Frontend: Image Review page** — Gate 2 UI with comparison
   - Files: `frontend/src/pages/ImageReview.tsx`

7. **Frontend: Video Preview page**
   - Files: `frontend/src/pages/VideoPreview.tsx`

## Build Order
1. Agent 0 (PPTX parser) — 1 day
2. Update Agent 2.5 (V4 pipeline) — 0.5 day
3. Image edit endpoint — 0.5 day
4. Video compiler — 0.5 day
5. Frontend: Extraction Review — 1 day
6. Frontend: Image Review — 1 day
7. Frontend: Video Preview + Download — 0.5 day
8. Integration + testing — 1 day

**Total: ~6 days**

## Cost per project: ~$6
- Extraction: $0.10 (Gemini)
- Images: $2.00 (13 rooms × Imagen + Gemini)
- Videos: $3.64 (13 rooms × Kling @ $0.28)
- Re-edits: +$0.50/room
