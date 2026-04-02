# FurniVision AI

Production-grade agentic pipeline that takes a furniture company's floor plan PDF and catalogue images, then automatically generates photorealistic room renders, a cinematic walkthrough video, and an interactive frame-based 3D viewer using Google's AI stack.

## Architecture

**5 AI Agents:**
1. **Parser** — Gemini 2.5 Pro Vision reads PDF + furniture images → structured JSON
2. **Planner** — Builds scene plan + 32 Imagen 3 prompts per room
3. **Generator** — Executes 32 concurrent Imagen 3 calls per room
4. **Validator** — OpenCV histogram matching + Gemini pairwise QC
5. **Animator** — Veo 3 video synthesis + Three.js viewer data

**2 Human Gates:**
- Gate 1: Confirm/correct extraction before generation
- Gate 2: Approve/reject per-room renders

## Quick Start

```bash
# 1. Copy env file and fill in your keys
cp .env.example .env

# 2. Start all services
docker-compose up

# 3. Open the UI
open http://localhost:5173
```

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
cd backend
pytest tests/ -v
```

## Environment Variables

See `.env.example` for all required configuration.

**Required:**
- `GOOGLE_API_KEY` — Gemini API key
- `GOOGLE_CLOUD_PROJECT` — GCP project ID
- `GCS_BUCKET_NAME` — Cloud Storage bucket

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Celery + Redis
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Three.js
- **AI:** Gemini 2.5 Pro, Imagen 3, Veo 3
- **Infrastructure:** Docker, GCS, Firestore
