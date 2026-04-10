"""FurniVision AI — Project, Room, and Furniture data models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FurnitureItem(BaseModel):
    id: str
    furniture_image_index: int
    item_name: str
    item_type: str
    color_primary: str | None = None
    color_secondary: str | None = None
    material: str | None = None
    style_tags: list[str] = []
    dims_estimated: dict | None = None  # {h_m, w_m, d_m}
    image_quality: str = "unclear"
    gcs_image_url: str = ""
    room_id: str | None = None
    notes: str = ""


class RoomGeometry(BaseModel):
    id: str
    label: str
    label_raw: str = ""
    polygon_relative: list[list[float]] = []
    area_sqm_estimated: float | None = None
    position_on_plan: str = ""
    furniture_items: list[FurnitureItem] = []
    notes: str = ""


class ProjectBrief(BaseModel):
    ceiling_height_m: float = 3.0
    floor_material: str = "polished concrete"
    wall_color: str = "matte white"
    overall_style: str = "modern commercial"
    lighting_mood: str = "bright natural daylight"
    overall_dimensions_m: dict | None = None  # {w, d}


# ---------------------------------------------------------------------------
# V5 Human-in-the-Loop models
# ---------------------------------------------------------------------------


class Product(BaseModel):
    """A furniture product extracted from a PPTX spec slide."""
    id: str
    name: str
    dimensions: str = ""
    image_path: str = ""  # local or GCS path to clean product render
    room_id: str = ""
    slide_index: int | None = None
    notes: str = ""


class GeneratedImage(BaseModel):
    """An AI-generated room render (base, refined, or edited)."""
    id: str
    room_id: str
    image_path: str = ""  # local or GCS path
    prompt_used: str = ""
    version: int = 1
    type: Literal["base", "refined", "edited"] = "base"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FloorPlan(BaseModel):
    """A floor plan image from the PPTX overview slide."""
    id: str
    floor_name: str = "ground"  # "ground" | "mezzanine"
    image_path: str = ""


class V5Room(BaseModel):
    """Room model for the V5 human-in-the-loop pipeline."""
    id: str
    label: str
    floor: str = "ground"

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if not data.get("floor"):
                data["floor"] = "ground"
        return data
    status: Literal[
        "pending",
        "extracted",
        "approved",
        "generating",
        "image_ready",
        "image_approved",
        "video_ready",
        "complete",
        "generation_failed",
        "video_failed",
    ] = "pending"
    layout_image_path: str = ""
    products: list[Product] = []
    generated_images: list[GeneratedImage] = []
    video_path: str | None = None
    feedback: list[str] = []


class Project(BaseModel):
    id: str
    name: str = "Untitled Project"
    status: Literal[
        "uploading",
        "extracting",
        "reviewing_extraction",
        "generating_images",
        "reviewing_images",
        "generating_videos",
        "complete",
        "failed",
        # Legacy V4 statuses (kept for compatibility)
        "analysing",
        "awaiting_gate1",
        "planning",
        "generating",
        "awaiting_gate2",
        "animating",
    ] = "uploading"
    # V5 fields
    spec_file_path: str = ""
    floor_plans: list[FloorPlan] = []
    v5_rooms: list[V5Room] = []
    logo_path: str | None = None
    music_path: str | None = None
    final_video_path: str | None = None
    # Legacy V4 fields
    rooms: list[RoomGeometry] = []
    brief: ProjectBrief = Field(default_factory=ProjectBrief)
    floorplan_gcs_path: str = ""
    furniture_gcs_paths: list[dict] = []  # [{id, filename, gcs_path}]
    reference_render_gcs_paths: list[dict] = []  # [{id, filename, gcs_path}]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
