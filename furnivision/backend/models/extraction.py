"""FurniVision AI — Extraction result models from Agent 1."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WallGeometry(BaseModel):
    start_relative: list[float]  # [x, y] 0.0-1.0
    end_relative: list[float]
    thickness_relative: float | None = None
    height_m: float | None = None


class DoorGeometry(BaseModel):
    room_id: str
    position_relative: list[float]
    width_m_estimated: float | None = None
    swing_direction: str | None = None


class WindowGeometry(BaseModel):
    room_id: str
    start_relative: list[float]
    end_relative: list[float]
    sill_height_m: float | None = None


class FurnitureAssignment(BaseModel):
    furniture_image_index: int
    room_id: str
    item_name: str
    confidence: float = 0.0
    assignment_basis: str = ""


class ScaleInfo(BaseModel):
    has_scale_bar: bool = False
    has_dimension_annotations: bool = False
    reference_dimension_found: str | None = None
    calibration_possible: bool = False
    notes: str = ""


class MissingField(BaseModel):
    field: str
    question: str
    default_guess: str | float | None = None
    importance: str = "medium"  # critical, high, medium, low


class ExtractionResult(BaseModel):
    project_id: str
    rooms: list["RoomGeometryExtracted"] = []
    walls: list[WallGeometry] = []
    doors: list[DoorGeometry] = []
    windows: list[WindowGeometry] = []
    furniture_assignments: list[FurnitureAssignment] = []
    furniture_items: list["FurnitureItemExtracted"] = []
    scale_info: ScaleInfo = Field(default_factory=ScaleInfo)
    missing_fields: list[MissingField] = []
    overall_style: str = ""
    lighting_cues: str = ""
    confidence_overall: float = 0.0
    raw_gemini_response: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoomGeometryExtracted(BaseModel):
    id: str
    label: str
    label_raw: str = ""
    polygon_relative: list[list[float]] = []
    area_sqm_estimated: float | None = None
    position_on_plan: str = ""
    notes: str = ""


class FurnitureItemExtracted(BaseModel):
    furniture_image_index: int
    item_name: str
    item_type: str = ""
    color_primary: str | None = None
    color_secondary: str | None = None
    material: str | None = None
    style_tags: list[str] = []
    dims_estimated: dict | None = None
    image_quality: str = "unclear"  # e.g. product_render, product_photo, scene_photo, context_render
    notes: str = ""
