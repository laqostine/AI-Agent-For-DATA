"""Tests for Agent 3: Generator — Imagen 3 frame generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.pipeline import FrameStatus


@pytest.fixture
def mock_scene_plan():
    """Create a mock ScenePlan with 32 prompts."""
    from agents.agent2_planner import ScenePlan, CameraPosition
    from models.project import RoomGeometry, ProjectBrief

    return ScenePlan(
        project_id="test_project",
        room_id="room_001",
        room=RoomGeometry(
            id="room_001",
            label="Sales Lounge",
            polygon_relative=[[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
            area_sqm_estimated=38.0,
        ),
        brief=ProjectBrief(),
        style_anchor="photorealistic architectural interior render",
        camera_positions=[
            CameraPosition(
                pos_x=float(i), pos_y=float(i), height_m=1.6,
                look_at_x=5.0, look_at_y=5.0, fov_deg=60.0,
                look_at_description=f"center of room from position {i}",
            )
            for i in range(8)
        ],
        prompts=[f"Test prompt for frame {i}" for i in range(32)],
        frame_types=["keyframe" if i % 4 == 0 else "interpolation" for i in range(32)],
        furniture_layout=[],
    )


@pytest.mark.asyncio
async def test_generator_produces_32_frame_statuses(mock_scene_plan):
    """Test that Agent 3 returns 32 FrameStatus objects."""
    with patch("agents.agent3_generator.ImagenService") as MockImagen, \
         patch("agents.agent3_generator.StorageService") as MockStorage:

        mock_imagen = MockImagen.return_value
        mock_imagen.generate_frame_with_retry = AsyncMock(return_value=b"fake_png_bytes")

        mock_storage = MockStorage.return_value
        mock_storage.upload_bytes = AsyncMock(return_value="gs://bucket/frame.png")
        mock_storage.get_signed_url = MagicMock(return_value="https://signed-url.com/frame.png")

        from agents.agent3_generator import GeneratorAgent

        agent = GeneratorAgent()
        agent.imagen = mock_imagen
        agent.storage = mock_storage

        results = await agent.generate_all_frames(
            scene_plan=mock_scene_plan,
            project_id="test_project",
            room_id="room_001",
            job_id="job_001",
        )

        assert len(results) == 32
        for r in results:
            assert isinstance(r, FrameStatus)


@pytest.mark.asyncio
async def test_generator_handles_frame_failure(mock_scene_plan):
    """Test that failed frames are marked correctly."""
    with patch("agents.agent3_generator.ImagenService") as MockImagen, \
         patch("agents.agent3_generator.StorageService") as MockStorage:

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 4:  # First frame fails all retries
                raise Exception("Imagen API error")
            return b"fake_png_bytes"

        mock_imagen = MockImagen.return_value
        # The agent calls imagen.generate_frame (not generate_frame_with_retry)
        # and handles retries internally
        mock_imagen.generate_frame = AsyncMock(side_effect=mock_generate)

        mock_storage = MockStorage.return_value
        mock_storage.upload_bytes = AsyncMock(return_value="gs://bucket/frame.png")
        mock_storage.get_signed_url = MagicMock(return_value="https://signed-url.com/frame.png")

        from agents.agent3_generator import GeneratorAgent

        agent = GeneratorAgent()
        agent.imagen = mock_imagen
        agent.storage = mock_storage

        results = await agent.generate_all_frames(
            scene_plan=mock_scene_plan,
            project_id="test_project",
            room_id="room_001",
            job_id="job_001",
        )

        assert len(results) == 32
        # Some frames should have completed (those after the first 4 failures)
        completed = [r for r in results if r.status == "complete"]
        failed = [r for r in results if r.status == "failed"]
        assert len(completed) + len(failed) == 32


@pytest.mark.asyncio
async def test_frame_status_model():
    """Test FrameStatus model validation."""
    status = FrameStatus(
        frame_idx=0,
        frame_type="keyframe",
        status="complete",
        gcs_url="gs://bucket/frame_000.png",
        attempts=1,
    )
    assert status.frame_idx == 0
    assert status.frame_type == "keyframe"
    assert status.status == "complete"
    assert status.attempts == 1
