"""FurniVision AI — Configuration from environment variables."""

import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Google AI
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

# fal.ai (video generation fallback — Kling image-to-video)
FAL_KEY: str = os.getenv("FAL_KEY", "")
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
VERTEX_AI_ENABLED: bool = os.getenv("VERTEX_AI_ENABLED", "false").lower() == "true"

# Google Cloud Storage
GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "furnivision-assets")
GCS_SIGNED_URL_EXPIRY_HOURS: int = int(os.getenv("GCS_SIGNED_URL_EXPIRY_HOURS", "168"))

# Firestore
FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "furnivision-db")

# Redis / Celery
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Pipeline Config
MAX_CONCURRENT_IMAGEN_CALLS: int = int(os.getenv("MAX_CONCURRENT_IMAGEN_CALLS", "8"))
FRAMES_PER_ROOM: int = int(os.getenv("FRAMES_PER_ROOM", "32"))
MAX_REGENERATION_ATTEMPTS: int = int(os.getenv("MAX_REGENERATION_ATTEMPTS", "3"))
QC_CONSISTENCY_THRESHOLD: float = float(os.getenv("QC_CONSISTENCY_THRESHOLD", "0.80"))
HUMAN_GATE_TIMEOUT_HOURS: int = int(os.getenv("HUMAN_GATE_TIMEOUT_HOURS", "48"))

# App
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS: list[str] = json.loads(
    os.getenv("CORS_ORIGINS", '["http://localhost:5173","https://frontend-three-nu-41.vercel.app"]')
)
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# Paths
TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "/tmp/furnivision"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# GCS path patterns
GCS_PATH_UPLOADS = "projects/{project_id}/uploads"
GCS_PATH_FLOORPLAN = "projects/{project_id}/uploads/floorplan.pdf"
GCS_PATH_FURNITURE = "projects/{project_id}/uploads/furniture/{item_id}.png"
GCS_PATH_REFERENCE = "projects/{project_id}/uploads/reference/{item_id}.jpg"
GCS_PATH_FRAMES_RAW = "projects/{project_id}/rooms/{room_id}/frames/raw/frame_{n:03d}.png"
GCS_PATH_FRAMES_GRADED = "projects/{project_id}/rooms/{room_id}/frames/graded/frame_{n:03d}.png"
GCS_PATH_VIDEO = "projects/{project_id}/rooms/{room_id}/video/room.mp4"
GCS_PATH_HLS = "projects/{project_id}/rooms/{room_id}/video/room.m3u8"
GCS_PATH_VIEWER_MANIFEST = "projects/{project_id}/rooms/{room_id}/viewer_manifest.json"
GCS_PATH_HERO_RENDERS = "projects/{project_id}/rooms/{room_id}/hero_renders/hero_{n}.webp"
GCS_PATH_REPORT = "projects/{project_id}/report/report.pdf"
GCS_PATH_MASTER_VIDEO = "projects/{project_id}/master_video/walkthrough.mp4"
