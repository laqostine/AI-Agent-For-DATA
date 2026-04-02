"""FurniVision AI — Agent 2: Planner — Scene plan and 32 prompts per room."""

import logging
import math
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from models.project import FurnitureItem, ProjectBrief, RoomGeometry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class CameraPosition(BaseModel):
    """A single virtual camera placement inside the room."""

    pos_x: float
    pos_y: float
    height_m: float
    look_at_x: float
    look_at_y: float
    fov_deg: float
    look_at_description: str


class ScenePlan(BaseModel):
    """Complete rendering plan for one room."""

    project_id: str
    room_id: str
    room: RoomGeometry
    brief: ProjectBrief
    style_anchor: str
    camera_positions: list[CameraPosition]  # 8 positions
    prompts: list[str]  # 32 prompts
    frame_types: list[str]  # "keyframe" or "interpolation" x32
    furniture_layout: list[dict]  # [{item_id, x_m, y_m, rotation_deg}]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_CAMERAS = 8
NUM_FRAMES = 32
FRAMES_PER_CAMERA = NUM_FRAMES // NUM_CAMERAS  # 4


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PlannerAgent:
    """Agent 2 — generates a ScenePlan with 8 camera positions and 32 prompts."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def plan(
        self,
        room: RoomGeometry,
        furniture_items: list[FurnitureItem],
        brief: ProjectBrief,
        project_style: str,
    ) -> ScenePlan:
        """Build a complete scene plan for one room.

        Parameters
        ----------
        room:
            Room geometry with polygon and metadata.
        furniture_items:
            Furniture items assigned to this room.
        brief:
            Project-level brief (ceiling height, materials, style).
        project_style:
            Overall style string inferred by Agent 1 (e.g. "modern minimalist").

        Returns
        -------
        ScenePlan
        """
        project_id = str(uuid.uuid4())
        room_id = room.id

        logger.info(
            "PlannerAgent.plan started — room=%s (%s), furniture=%d items",
            room_id, room.label, len(furniture_items),
        )

        # 1. Build furniture layout
        furniture_layout = self._build_furniture_layout(room, furniture_items)
        logger.info("Furniture layout: %d items placed", len(furniture_layout))

        # 2. Design 8 camera positions
        camera_positions = self._design_camera_positions(room, brief)
        logger.info("Designed %d camera positions", len(camera_positions))

        # 3. Build style anchor string
        materials_str = self._collect_materials(furniture_items)
        style_anchor = self._build_style_anchor(brief, project_style, materials_str)
        logger.info("Style anchor: %s", style_anchor[:120])

        # 4. Generate 32 prompts with K,I,I,I pattern
        prompts, frame_types = self._generate_prompts(
            room=room,
            furniture_items=furniture_items,
            furniture_layout=furniture_layout,
            camera_positions=camera_positions,
            style_anchor=style_anchor,
            brief=brief,
        )
        logger.info(
            "Generated %d prompts (%d keyframes, %d interpolations)",
            len(prompts),
            sum(1 for ft in frame_types if ft == "keyframe"),
            sum(1 for ft in frame_types if ft == "interpolation"),
        )

        scene_plan = ScenePlan(
            project_id=project_id,
            room_id=room_id,
            room=room,
            brief=brief,
            style_anchor=style_anchor,
            camera_positions=camera_positions,
            prompts=prompts,
            frame_types=frame_types,
            furniture_layout=furniture_layout,
        )

        logger.info("ScenePlan complete for room %s", room_id)
        return scene_plan

    # ------------------------------------------------------------------
    # 1. Furniture layout
    # ------------------------------------------------------------------

    def _build_furniture_layout(
        self,
        room: RoomGeometry,
        furniture_items: list[FurnitureItem],
    ) -> list[dict]:
        """Assign spatial positions to furniture items within the room polygon.

        Uses interior-design heuristics:
        - Large seating faces the room centre
        - Tables go near centre
        - Storage / shelves along walls
        - Rugs centred in open space
        - Lamps near seating or corners
        """
        if not room.polygon_relative:
            logger.warning("Room %s has no polygon — using default rectangle", room.id)
            polygon = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
        else:
            polygon = room.polygon_relative

        # Compute bounding box and centre
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        h = max_y - min_y

        layout: list[dict] = []

        # Categorise items by type for placement priority
        type_zones = {
            "sofa": "centre_facing",
            "table": "centre",
            "chair": "around_table",
            "bed": "wall_centre",
            "desk": "wall",
            "shelf": "wall",
            "wardrobe": "wall",
            "lamp": "corner",
            "rug": "centre_floor",
            "other": "distributed",
        }

        wall_items: list[tuple[int, FurnitureItem]] = []
        centre_items: list[tuple[int, FurnitureItem]] = []
        corner_items: list[tuple[int, FurnitureItem]] = []

        for idx, item in enumerate(furniture_items):
            zone = type_zones.get(item.item_type, "distributed")
            if zone in ("wall", "wall_centre", "centre_facing"):
                wall_items.append((idx, item))
            elif zone in ("corner",):
                corner_items.append((idx, item))
            else:
                centre_items.append((idx, item))

        # Place wall items along perimeter
        wall_positions = self._distribute_along_walls(polygon, len(wall_items))
        for (idx, item), (px, py, angle) in zip(wall_items, wall_positions):
            layout.append({
                "item_id": item.id,
                "x_m": round(px, 3),
                "y_m": round(py, 3),
                "rotation_deg": round(angle, 1),
            })

        # Place centre items in a grid around the room centre
        if centre_items:
            grid_size = math.ceil(math.sqrt(len(centre_items)))
            spacing_x = w * 0.4 / max(grid_size, 1)
            spacing_y = h * 0.4 / max(grid_size, 1)
            start_x = cx - (grid_size - 1) * spacing_x / 2
            start_y = cy - (grid_size - 1) * spacing_y / 2

            for i, (idx, item) in enumerate(centre_items):
                gx = i % grid_size
                gy = i // grid_size
                px = start_x + gx * spacing_x
                py = start_y + gy * spacing_y
                layout.append({
                    "item_id": item.id,
                    "x_m": round(px, 3),
                    "y_m": round(py, 3),
                    "rotation_deg": 0.0,
                })

        # Place corner items in room corners
        corners = [
            (min_x + w * 0.05, min_y + h * 0.05),
            (max_x - w * 0.05, min_y + h * 0.05),
            (max_x - w * 0.05, max_y - h * 0.05),
            (min_x + w * 0.05, max_y - h * 0.05),
        ]
        for i, (idx, item) in enumerate(corner_items):
            corner = corners[i % len(corners)]
            layout.append({
                "item_id": item.id,
                "x_m": round(corner[0], 3),
                "y_m": round(corner[1], 3),
                "rotation_deg": 45.0 * (i % 4),
            })

        return layout

    def _distribute_along_walls(
        self,
        polygon: list[list[float]],
        count: int,
    ) -> list[tuple[float, float, float]]:
        """Distribute *count* items along the walls of *polygon*.

        Returns list of (x, y, rotation_deg) tuples.  Rotation faces the
        item toward the room interior.
        """
        if count == 0:
            return []

        # Compute wall segments and their lengths
        segments: list[tuple[list[float], list[float], float]] = []
        total_length = 0.0
        n = len(polygon)
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            length = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
            segments.append((p1, p2, length))
            total_length += length

        # Place items evenly along the total perimeter
        positions: list[tuple[float, float, float]] = []
        spacing = total_length / (count + 1)

        for item_idx in range(count):
            target_dist = spacing * (item_idx + 1)
            cumulative = 0.0

            for p1, p2, seg_len in segments:
                if cumulative + seg_len >= target_dist:
                    t = (target_dist - cumulative) / seg_len if seg_len > 0 else 0.5
                    x = p1[0] + t * (p2[0] - p1[0])
                    y = p1[1] + t * (p2[1] - p1[1])

                    # Compute inward-facing angle
                    wall_angle = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
                    # Face inward = perpendicular to wall, toward interior
                    rotation = (wall_angle + 90) % 360

                    # Offset slightly inward from wall
                    offset = 0.02
                    nx = math.cos(math.radians(rotation)) * offset
                    ny = math.sin(math.radians(rotation)) * offset
                    positions.append((x + nx, y + ny, rotation))
                    break
                cumulative += seg_len
            else:
                # Fallback: place at polygon centroid
                cx = sum(p[0] for p in polygon) / len(polygon)
                cy = sum(p[1] for p in polygon) / len(polygon)
                positions.append((cx, cy, 0.0))

        return positions

    # ------------------------------------------------------------------
    # 2. Camera positions
    # ------------------------------------------------------------------

    def _design_camera_positions(
        self,
        room: RoomGeometry,
        brief: ProjectBrief,
    ) -> list[CameraPosition]:
        """Design 8 camera positions distributed around the room.

        Camera 0 is the entrance wide shot.  Cameras 1-7 are spaced around
        the room at varying heights and FOVs for visual diversity.
        """
        polygon = room.polygon_relative or [
            [0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]
        ]

        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        h = max_y - min_y

        ceiling = brief.ceiling_height_m

        # Define 8 camera templates around the room
        # (offset_from_edge_x, offset_from_edge_y, height_fraction, fov, description)
        camera_templates = [
            # Camera 0: Entrance wide shot — near bottom edge, looking in
            (0.5, 0.05, 0.55, 75.0, "entrance wide shot looking into room"),
            # Camera 1: Left wall, eye level
            (0.08, 0.35, 0.50, 60.0, "left wall perspective toward opposite wall"),
            # Camera 2: Right wall, slightly elevated
            (0.92, 0.40, 0.60, 55.0, "right wall elevated view toward centre"),
            # Camera 3: Far corner, high angle
            (0.90, 0.90, 0.75, 70.0, "far corner high angle overlooking room"),
            # Camera 4: Centre-back, standard height
            (0.50, 0.92, 0.50, 65.0, "back wall centre view toward entrance"),
            # Camera 5: Left-back diagonal
            (0.12, 0.85, 0.55, 60.0, "left-back diagonal across room"),
            # Camera 6: Right-front, low angle detail
            (0.85, 0.15, 0.35, 50.0, "right-front low angle detail shot"),
            # Camera 7: Centre elevated overview
            (0.50, 0.50, 0.80, 80.0, "centre elevated overview of entire room"),
        ]

        cameras: list[CameraPosition] = []
        for i, (rx, ry, h_frac, fov, desc) in enumerate(camera_templates):
            pos_x = min_x + rx * w
            pos_y = min_y + ry * h
            height = ceiling * h_frac

            # Look-at point: generally toward room centre, with slight variation
            look_x = cx + (0.5 - rx) * w * 0.1
            look_y = cy + (0.5 - ry) * h * 0.1

            cameras.append(CameraPosition(
                pos_x=round(pos_x, 4),
                pos_y=round(pos_y, 4),
                height_m=round(height, 2),
                look_at_x=round(look_x, 4),
                look_at_y=round(look_y, 4),
                fov_deg=fov,
                look_at_description=desc,
            ))

        return cameras

    # ------------------------------------------------------------------
    # 3. Style anchor
    # ------------------------------------------------------------------

    def _build_style_anchor(
        self,
        brief: ProjectBrief,
        project_style: str,
        materials: str,
    ) -> str:
        """Build the canonical style-anchor string for all prompts.

        Format: "photorealistic architectural interior render, {style},
        {floor} floor, {wall} walls, {height}m ceiling height, natural
        daylight from windows, professional interior photography, shot on
        Canon EOS R5, 35mm lens, f/4.0, ISO 200, warm neutral colour
        grade, 8K ultra detailed, no people, no text, furniture materials:
        {materials}"
        """
        style = project_style or brief.overall_style or "modern commercial"
        floor = brief.floor_material or "polished concrete"
        wall = brief.wall_color or "matte white"
        height = brief.ceiling_height_m

        anchor = (
            f"photorealistic architectural interior render, {style}, "
            f"{floor} floor, {wall} walls, {height}m ceiling height, "
            f"natural daylight from windows, professional interior photography, "
            f"shot on Canon EOS R5, 35mm lens, f/4.0, ISO 200, "
            f"warm neutral colour grade, 8K ultra detailed, no people, no text, "
            f"furniture materials: {materials}"
        )
        return anchor

    def _collect_materials(self, items: list[FurnitureItem]) -> str:
        """Collect unique material descriptions from furniture items."""
        materials: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item.material and item.material.lower() not in seen:
                materials.append(item.material)
                seen.add(item.material.lower())
        return ", ".join(materials) if materials else "mixed materials"

    # ------------------------------------------------------------------
    # 4. Prompt generation — 32 frames, K,I,I,I pattern
    # ------------------------------------------------------------------

    def _generate_prompts(
        self,
        room: RoomGeometry,
        furniture_items: list[FurnitureItem],
        furniture_layout: list[dict],
        camera_positions: list[CameraPosition],
        style_anchor: str,
        brief: ProjectBrief,
    ) -> tuple[list[str], list[str]]:
        """Generate 32 frame prompts with K,I,I,I,K,I,I,I x 8 pattern.

        Returns (prompts, frame_types) where frame_types[i] is
        "keyframe" or "interpolation".
        """
        prompts: list[str] = []
        frame_types: list[str] = []

        # Build a furniture description for prompt inclusion
        furniture_desc = self._build_furniture_description(furniture_items)
        room_desc = self._build_room_description(room, brief)

        # Build layout lookup for visible furniture per camera
        layout_lookup = {item["item_id"]: item for item in furniture_layout}
        item_lookup = {item.id: item for item in furniture_items}

        for frame_idx in range(NUM_FRAMES):
            camera_idx = frame_idx // FRAMES_PER_CAMERA
            local_idx = frame_idx % FRAMES_PER_CAMERA
            is_keyframe = (local_idx == 0)

            frame_type = "keyframe" if is_keyframe else "interpolation"
            frame_types.append(frame_type)

            camera = camera_positions[camera_idx]

            # Determine which furniture items are visible from this camera
            visible_items = self._get_visible_furniture(
                camera, furniture_layout, item_lookup
            )
            visible_desc = self._describe_visible_furniture(visible_items)

            if frame_idx == 0:
                # Frame 0: entrance wide shot
                prompt = (
                    f"{style_anchor}. "
                    f"Entrance wide-angle shot of the {room.label}. "
                    f"{room_desc}. "
                    f"Camera at entrance doorway, eye level ({camera.height_m}m), "
                    f"FOV {camera.fov_deg} degrees, looking into the full room. "
                    f"Visible furniture: {visible_desc}. "
                    f"First frame establishing the complete space, "
                    f"warm inviting atmosphere, all architectural details visible."
                )
            elif is_keyframe:
                # Keyframes: full scene description from new camera angle
                prompt = (
                    f"{style_anchor}. "
                    f"{room.label}, {camera.look_at_description}. "
                    f"{room_desc}. "
                    f"Camera position: ({camera.pos_x:.2f}, {camera.pos_y:.2f}) "
                    f"at {camera.height_m}m height, "
                    f"FOV {camera.fov_deg} degrees, "
                    f"looking at ({camera.look_at_x:.2f}, {camera.look_at_y:.2f}). "
                    f"Visible furniture: {visible_desc}. "
                    f"Consistent lighting and materials with previous frames, "
                    f"same room, same time of day."
                )
            else:
                # Interpolation frames: subtle transition from previous keyframe
                prev_camera = camera_positions[max(0, camera_idx - 1)] if local_idx == 1 else camera
                transition_fraction = local_idx / FRAMES_PER_CAMERA

                prompt = (
                    f"{style_anchor}. "
                    f"{room.label}, smooth camera transition. "
                    f"{room_desc}. "
                    f"Camera smoothly moving from previous position toward "
                    f"{camera.look_at_description}. "
                    f"Transition progress: {transition_fraction:.0%}. "
                    f"Height {camera.height_m}m, FOV {camera.fov_deg} degrees. "
                    f"Visible furniture: {visible_desc}. "
                    f"CRITICAL: maintain exact same furniture placement, wall colours, "
                    f"floor material, and lighting as the previous frame. "
                    f"Only the viewing angle changes slightly."
                )

            prompts.append(prompt)

        return prompts, frame_types

    # ------------------------------------------------------------------
    # Prompt helper methods
    # ------------------------------------------------------------------

    def _build_room_description(self, room: RoomGeometry, brief: ProjectBrief) -> str:
        """Build a concise room description for prompt inclusion."""
        parts = [f"{room.label}"]
        if room.area_sqm_estimated:
            parts.append(f"approximately {room.area_sqm_estimated:.0f} sqm")
        parts.append(f"{brief.ceiling_height_m}m ceiling height")
        parts.append(f"{brief.floor_material} floor")
        parts.append(f"{brief.wall_color} walls")
        if brief.lighting_mood:
            parts.append(brief.lighting_mood)
        return ", ".join(parts)

    def _build_furniture_description(self, items: list[FurnitureItem]) -> str:
        """Build a summary of all furniture in the room."""
        if not items:
            return "empty room, no furniture"
        descriptions: list[str] = []
        for item in items:
            desc = item.item_name
            if item.color_primary:
                desc = f"{item.color_primary} {desc}"
            if item.material:
                desc += f" ({item.material})"
            descriptions.append(desc)
        return "; ".join(descriptions)

    def _get_visible_furniture(
        self,
        camera: CameraPosition,
        furniture_layout: list[dict],
        item_lookup: dict[str, FurnitureItem],
    ) -> list[FurnitureItem]:
        """Determine which furniture items are visible from a camera position.

        Uses a simplified FOV cone check based on angle from camera to item
        relative to the camera look-at direction.
        """
        visible: list[FurnitureItem] = []
        cam_angle = math.atan2(
            camera.look_at_y - camera.pos_y,
            camera.look_at_x - camera.pos_x,
        )
        half_fov = math.radians(camera.fov_deg / 2)

        for placement in furniture_layout:
            item_id = placement["item_id"]
            item = item_lookup.get(item_id)
            if item is None:
                continue

            item_angle = math.atan2(
                placement["y_m"] - camera.pos_y,
                placement["x_m"] - camera.pos_x,
            )

            # Angular difference
            diff = abs(item_angle - cam_angle)
            if diff > math.pi:
                diff = 2 * math.pi - diff

            if diff <= half_fov * 1.2:  # slight margin
                visible.append(item)

        # If nothing visible (e.g. bad geometry), include all items
        if not visible and item_lookup:
            visible = list(item_lookup.values())

        return visible

    def _describe_visible_furniture(self, items: list[FurnitureItem]) -> str:
        """Build a comma-separated description of visible furniture."""
        if not items:
            return "no furniture in view"
        parts: list[str] = []
        for item in items[:8]:  # cap at 8 to keep prompt manageable
            desc = item.item_name
            if item.color_primary:
                desc = f"{item.color_primary} {desc}"
            parts.append(desc)
        result = ", ".join(parts)
        if len(items) > 8:
            result += f", and {len(items) - 8} more items"
        return result
