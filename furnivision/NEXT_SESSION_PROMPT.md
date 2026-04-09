# Prompt for Next Session

Copy-paste this to start the new session:

---

Build the FurniVision V5 human-in-the-loop system. Read the plan at `/Users/bera/Documents/GitHub/AI-Agent-For-DATA/furnivision/PLAN_V5_HUMAN_IN_THE_LOOP.md` first.

## Context
This is a furniture visualization tool for Persona Office Furniture (Turkish company). Their client Forthing (Chinese car brand) is building a dealership. Persona furnishes it. The system takes a PPTX spec document (room-by-room with product images) and generates 3D walkthrough videos showing the exact Persona products in each room.

## What already exists
- FastAPI backend at `furnivision/backend/` with agents 1-5, human gates, Gemini/Imagen/Kling services
- React frontend at `furnivision/frontend/`
- V4 image pipeline: Imagen 4 (16:9 base) → Gemini Flash Image (multi-ref refinement, 3 attempts) → Kling video (7s) → ffmpeg (1920x1080)
- Agent 2.5 SceneComposer already built
- fal.ai Kling video service + Veo fallback
- Clean product images extracted from PPTX at `/tmp/furnivision/pptx_products/`
- Room-to-product mapping at `/tmp/furnivision/v3_spec/room_products.json`
- Working V4 output at `/tmp/furnivision/forthing_v4/`

## What to build (in order)
1. **Agent 0: PPTX Parser** (`backend/agents/agent0_pptx_parser.py`) — extracts slides → rooms + product images + labels + dimensions. Uses python-pptx for image extraction + Gemini for understanding slide structure.

2. **Update Agent 2.5** — integrate V4 pipeline: Imagen base 16:9 → Gemini Flash Image multi-ref refinement with structured JSON prompts → best-of-3 selection.

3. **Image Edit endpoint** (`backend/api/routes/edit.py`) — takes existing room image + feedback text + product reference → Gemini Flash Image targeted edit.

4. **Video Compiler** (`backend/services/video_compiler.py`) — concat room videos + ambient music + logo end card via ffmpeg.

5. **Frontend pages:**
   - `ExtractionReview.tsx` — Gate 1: review rooms + products, edit, approve
   - `ImageReview.tsx` — Gate 2: side-by-side comparison, feedback, re-edit, approve
   - `VideoPreview.tsx` — play videos, compile final, download

## Key technical details
- Gemini Flash Image (`gemini-2.5-flash-image`) for img2img with `response_modalities=["IMAGE", "TEXT"]`
- Product images passed as `inline_data` (up to 5 per request)
- Imagen 4 Fast (`imagen-4.0-fast-generate-001`) for 16:9 base renders with `aspect_ratio="16:9"`
- Kling via fal.ai (`fal-ai/kling-video/v2.1/standard/image-to-video`) for 10s video trimmed to 7s
- All keyframes must be 16:9 (1536x864) before video generation
- `google.genai` SDK (new), NOT `google.generativeai` (deprecated)

## Client feedback to handle
- Conference chairs MUST have visible casters (wheels)
- Bar table must show blue A-frame legs (not solid block)
- Kids room: simple — just red table + orange chairs + bench, no extras
- GM office uses Dapper DARK variant (walnut + full black panels)
- Workstation has silver A-legs + blue screens (not red legs)

## Environment
- `.env` has GOOGLE_API_KEY, FAL_KEY
- Local dev: in-memory state, `/tmp/furnivision/storage/` for files
- Python 3.14, venv at `backend/venv/`

Start by reading the plan, then build Agent 0 (PPTX parser) first.
