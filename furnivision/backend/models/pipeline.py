"""FurniVision AI — Pipeline state models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FrameStatus(BaseModel):
    frame_idx: int
    frame_type: Literal["keyframe", "interpolation"]
    status: Literal["pending", "generating", "complete", "failed", "retrying"] = "pending"
    gcs_url: str | None = None
    attempts: int = 0
    error_message: str | None = None
    completed_at: datetime | None = None


class RoomPipelineState(BaseModel):
    room_id: str
    label: str
    status: Literal[
        "pending",
        "planning",
        "generating",
        "validating",
        "animating",
        "complete",
        "rejected",
        "failed",
    ] = "pending"
    frames: list[FrameStatus] = []
    preview_url: str | None = None
    hero_frame_urls: list[str] = []
    video_url: str | None = None
    qc_score: float | None = None
    rejection_count: int = 0
    rejection_feedback: str | None = None


class PipelineState(BaseModel):
    project_id: str
    job_id: str
    current_stage: int = 0  # 0-5
    stage_name: str = "initializing"
    rooms: list[RoomPipelineState] = []
    gate_1_confirmed: bool = False
    gate_2_rooms_approved: dict[str, bool] = {}  # room_id → approved
    started_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_complete_at: datetime | None = None
    error: str | None = None
