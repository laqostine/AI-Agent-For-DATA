"""Tests for Agent 2: Planner — Scene plan + 32 prompts per room."""

import pytest
from unittest.mock import AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.project import RoomGeometry, FurnitureItem, ProjectBrief


@pytest.fixture
def sample_room():
    return RoomGeometry(
        id="room_001",
        label="Sales Lounge",
        polygon_relative=[[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
        area_sqm_estimated=38.0,
    )


@pytest.fixture
def sample_furniture():
    return [
        FurnitureItem(
            id="furn_001",
            furniture_image_index=0,
            item_name="Grey three-seat sofa",
            item_type="sofa",
            color_primary="#9CA3AF",
            material="fabric",
            style_tags=["modern", "minimalist"],
            gcs_image_url="gs://bucket/furniture/001.png",
            room_id="room_001",
        ),
        FurnitureItem(
            id="furn_002",
            furniture_image_index=1,
            item_name="Walnut coffee table",
            item_type="table",
            color_primary="#8B4513",
            material="wood",
            style_tags=["modern"],
            gcs_image_url="gs://bucket/furniture/002.png",
            room_id="room_001",
        ),
    ]


@pytest.fixture
def sample_brief():
    return ProjectBrief(
        ceiling_height_m=3.5,
        floor_material="marble",
        wall_color="matte white",
        overall_style="modern commercial showroom",
        lighting_mood="bright natural daylight",
    )


@pytest.mark.asyncio
async def test_planner_generates_32_prompts(sample_room, sample_furniture, sample_brief):
    """Test that Agent 2 generates exactly 32 prompts."""
    from agents.agent2_planner import PlannerAgent

    agent = PlannerAgent()
    plan = await agent.plan(
        room=sample_room,
        furniture_items=sample_furniture,
        brief=sample_brief,
        project_style="modern commercial showroom",
    )

    assert len(plan.prompts) == 32
    assert len(plan.frame_types) == 32
    assert len(plan.camera_positions) == 8


@pytest.mark.asyncio
async def test_planner_keyframe_pattern(sample_room, sample_furniture, sample_brief):
    """Test that frame types follow K,I,I,I pattern."""
    from agents.agent2_planner import PlannerAgent

    agent = PlannerAgent()
    plan = await agent.plan(
        room=sample_room,
        furniture_items=sample_furniture,
        brief=sample_brief,
        project_style="modern commercial showroom",
    )

    # 8 keyframes at indices 0, 4, 8, 12, 16, 20, 24, 28
    for i in range(32):
        if i % 4 == 0:
            assert plan.frame_types[i] == "keyframe", f"Frame {i} should be keyframe"
        else:
            assert plan.frame_types[i] == "interpolation", f"Frame {i} should be interpolation"


@pytest.mark.asyncio
async def test_planner_style_anchor_consistency(sample_room, sample_furniture, sample_brief):
    """Test that style anchor is consistent across all prompts."""
    from agents.agent2_planner import PlannerAgent

    agent = PlannerAgent()
    plan = await agent.plan(
        room=sample_room,
        furniture_items=sample_furniture,
        brief=sample_brief,
        project_style="modern commercial showroom",
    )

    assert plan.style_anchor != ""
    # Style anchor should appear in every prompt
    for i, prompt in enumerate(plan.prompts):
        assert plan.style_anchor in prompt, f"Style anchor missing from prompt {i}"


@pytest.mark.asyncio
async def test_planner_first_frame_is_entrance(sample_room, sample_furniture, sample_brief):
    """Test that Frame 0 is always the entrance wide shot."""
    from agents.agent2_planner import PlannerAgent

    agent = PlannerAgent()
    plan = await agent.plan(
        room=sample_room,
        furniture_items=sample_furniture,
        brief=sample_brief,
        project_style="modern commercial showroom",
    )

    assert "entrance" in plan.prompts[0].lower() or "wide" in plan.prompts[0].lower()
