"""FurniVision AI — Project, Room, and Furniture data models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    image_quality: Literal["product_render", "product_photo", "scene_photo", "unclear"] = "unclear"
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


class Project(BaseModel):
    id: str
    name: str = "Untitled Project"
    status: Literal[
        "uploading",
        "analysing",
        "awaiting_gate1",
        "planning",
        "generating",
        "awaiting_gate2",
        "animating",
        "complete",
        "failed",
    ] = "uploading"
    rooms: list[RoomGeometry] = []
    brief: ProjectBrief = Field(default_factory=ProjectBrief)
    floorplan_gcs_path: str = ""
    furniture_gcs_paths: list[dict] = []  # [{id, filename, gcs_path}]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
