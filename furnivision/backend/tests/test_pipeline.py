"""Tests for the pipeline orchestrator and state management."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.project import Project, ProjectBrief, RoomGeometry, FurnitureItem
from models.pipeline import PipelineState, RoomPipelineState, FrameStatus
from models.extraction import ExtractionResult


@pytest.fixture
def sample_project():
    return Project(
        id="test_project_001",
        name="Test Showroom",
        status="uploading",
        rooms=[
            RoomGeometry(
                id="room_001",
                label="Sales Lounge",
                polygon_relative=[[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
                area_sqm_estimated=38.0,
                furniture_items=[
                    FurnitureItem(
                        id="furn_001",
                        furniture_image_index=0,
                        item_name="Grey sofa",
                        item_type="sofa",
                        gcs_image_url="gs://bucket/furn/001.png",
                        room_id="room_001",
                    )
                ],
            )
        ],
        brief=ProjectBrief(
            ceiling_height_m=3.5,
            floor_material="marble",
            wall_color="matte white",
        ),
        floorplan_gcs_path="gs://bucket/uploads/floorplan.pdf",
    )


def test_project_model_creation(sample_project):
    """Test Project model creates correctly."""
    assert sample_project.id == "test_project_001"
    assert sample_project.status == "uploading"
    assert len(sample_project.rooms) == 1
    assert sample_project.rooms[0].label == "Sales Lounge"
    assert len(sample_project.rooms[0].furniture_items) == 1


def test_pipeline_state_model():
    """Test PipelineState model with room states."""
    state = PipelineState(
        project_id="test_001",
        job_id="job_001",
        current_stage=2,
        stage_name="agent3_generating",
        rooms=[
            RoomPipelineState(
                room_id="room_001",
                label="Sales Lounge",
                status="generating",
                frames=[
                    FrameStatus(
                        frame_idx=i,
                        frame_type="keyframe" if i % 4 == 0 else "interpolation",
                        status="complete" if i < 10 else "pending",
                    )
                    for i in range(32)
                ],
            )
        ],
        gate_1_confirmed=True,
    )

    assert state.current_stage == 2
    assert state.gate_1_confirmed is True
    assert len(state.rooms) == 1
    assert len(state.rooms[0].frames) == 32
    completed = [f for f in state.rooms[0].frames if f.status == "complete"]
    assert len(completed) == 10


def test_pipeline_state_gate_tracking():
    """Test gate confirmation tracking."""
    state = PipelineState(
        project_id="test_001",
        job_id="job_001",
        gate_1_confirmed=False,
        gate_2_rooms_approved={},
    )

    assert state.gate_1_confirmed is False
    assert len(state.gate_2_rooms_approved) == 0

    # Simulate gate confirmations
    state.gate_1_confirmed = True
    state.gate_2_rooms_approved["room_001"] = True
    state.gate_2_rooms_approved["room_002"] = False

    assert state.gate_1_confirmed is True
    assert state.gate_2_rooms_approved["room_001"] is True
    assert state.gate_2_rooms_approved["room_002"] is False


def test_room_pipeline_state_transitions():
    """Test valid room status transitions."""
    valid_statuses = [
        "pending", "planning", "generating", "validating",
        "animating", "complete", "rejected", "failed",
    ]
    for status in valid_statuses:
        room = RoomPipelineState(
            room_id="room_001",
            label="Test Room",
            status=status,
        )
        assert room.status == status


@pytest.mark.asyncio
async def test_state_manager_in_memory_fallback():
    """Test that StateManager falls back to in-memory when Firestore unavailable."""
    with patch("pipeline.state.firestore") as mock_firestore:
        mock_firestore.AsyncClient.side_effect = Exception("No Firestore")

        from pipeline.state import StateManager

        manager = StateManager()

        project = Project(
            id="test_001",
            name="Test",
            status="uploading",
        )
        await manager.create_project(project)
        retrieved = await manager.get_project("test_001")

        assert retrieved is not None
        assert retrieved.id == "test_001"
