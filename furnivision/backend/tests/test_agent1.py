"""Tests for Agent 1: Parser — PDF → structured JSON extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.extraction import ExtractionResult, RoomGeometryExtracted, MissingField


MOCK_GEMINI_RESPONSE = {
    "rooms": [
        {
            "id": "room_001",
            "label": "Sales Lounge",
            "label_raw": "Sales lounge",
            "polygon_relative": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
            "area_sqm_estimated": 38.0,
            "position_on_plan": "bottom-left",
            "notes": "open plan area",
        },
        {
            "id": "room_002",
            "label": "Reception",
            "label_raw": "Reception",
            "polygon_relative": [[0.5, 0.0], [0.8, 0.0], [0.8, 0.3], [0.5, 0.3]],
            "area_sqm_estimated": 24.0,
            "position_on_plan": "top-right",
            "notes": "",
        },
        {
            "id": "room_003",
            "label": "Meeting Room",
            "label_raw": "Meeting room",
            "polygon_relative": [[0.6, 0.4], [0.9, 0.4], [0.9, 0.7], [0.6, 0.7]],
            "area_sqm_estimated": 20.0,
            "position_on_plan": "center-right",
            "notes": "",
        },
        {
            "id": "room_004",
            "label": "Office",
            "label_raw": "Office",
            "polygon_relative": [[0.0, 0.6], [0.3, 0.6], [0.3, 0.9], [0.0, 0.9]],
            "area_sqm_estimated": 15.0,
            "position_on_plan": "bottom-left",
            "notes": "",
        },
    ],
    "walls": [],
    "doors": [],
    "windows": [],
    "furniture_assignments": [],
    "furniture_items": [],
    "scale_info": {
        "has_scale_bar": False,
        "has_dimension_annotations": False,
        "reference_dimension_found": None,
        "calibration_possible": False,
        "notes": "No scale reference found",
    },
    "missing_fields": [
        {
            "field": "ceiling_height_m",
            "question": "What is the ceiling height of the space?",
            "default_guess": 3.0,
            "importance": "high",
        },
        {
            "field": "floor_material",
            "question": "What is the floor material?",
            "default_guess": "polished concrete",
            "importance": "high",
        },
        {
            "field": "overall_dimensions",
            "question": "What are the total floor dimensions?",
            "default_guess": None,
            "importance": "critical",
        },
    ],
    "overall_style": "modern commercial showroom",
    "lighting_cues": "large windows on north wall",
    "confidence_overall": 0.78,
}


@pytest.mark.asyncio
async def test_agent1_extracts_rooms():
    """Test that Agent 1 correctly parses Gemini response into ExtractionResult."""
    with patch("agents.agent1_parser.GeminiService") as MockGemini, \
         patch("agents.agent1_parser.PDFProcessor") as MockPDF:

        mock_gemini = MockGemini.return_value
        mock_gemini.analyze_images_structured = AsyncMock(return_value=MOCK_GEMINI_RESPONSE)

        mock_pdf = MockPDF.return_value
        mock_pdf.convert_to_images.return_value = [b"fake_png_bytes"]
        mock_pdf.extract_embedded_images.return_value = []

        from agents.agent1_parser import ParserAgent

        agent = ParserAgent()
        agent.gemini = mock_gemini
        agent.pdf_processor = mock_pdf

        result = await agent.parse(
            pdf_path="tests/fixtures/GROUND_FLOOR.pdf",
            furniture_images=[],
            brief_data=None,
        )

        assert isinstance(result, ExtractionResult)
        assert result.confidence_overall > 0.5
        assert len(result.rooms) >= 4
        assert any(
            r.label.lower() in ["sales lounge", "sales"] for r in result.rooms
        )
        assert len(result.missing_fields) > 0
        assert result.raw_gemini_response != ""


@pytest.mark.asyncio
async def test_agent1_handles_invalid_json_retry():
    """Test that Agent 1 retries on invalid JSON from Gemini."""
    with patch("agents.agent1_parser.GeminiService") as MockGemini, \
         patch("agents.agent1_parser.PDFProcessor") as MockPDF:

        mock_gemini = MockGemini.return_value
        # First call returns invalid JSON, second returns valid
        mock_gemini.analyze_images_structured = AsyncMock(
            side_effect=[
                ValueError("Invalid JSON"),
                MOCK_GEMINI_RESPONSE,
            ]
        )

        mock_pdf = MockPDF.return_value
        mock_pdf.convert_to_images.return_value = [b"fake_png_bytes"]
        mock_pdf.extract_embedded_images.return_value = []

        from agents.agent1_parser import ParserAgent

        agent = ParserAgent()
        agent.gemini = mock_gemini
        agent.pdf_processor = mock_pdf

        result = await agent.parse(
            pdf_path="tests/fixtures/GROUND_FLOOR.pdf",
            furniture_images=[],
            brief_data=None,
        )

        assert isinstance(result, ExtractionResult)
        assert len(result.rooms) >= 4


@pytest.mark.asyncio
async def test_agent1_returns_partial_on_total_failure():
    """Test that Agent 1 returns partial result with confidence 0.0 on complete failure."""
    with patch("agents.agent1_parser.GeminiService") as MockGemini, \
         patch("agents.agent1_parser.PDFProcessor") as MockPDF:

        mock_gemini = MockGemini.return_value
        mock_gemini.analyze_images_structured = AsyncMock(
            side_effect=ValueError("Invalid JSON")
        )

        mock_pdf = MockPDF.return_value
        mock_pdf.convert_to_images.return_value = [b"fake_png_bytes"]
        mock_pdf.extract_embedded_images.return_value = []

        from agents.agent1_parser import ParserAgent

        agent = ParserAgent()
        agent.gemini = mock_gemini
        agent.pdf_processor = mock_pdf

        result = await agent.parse(
            pdf_path="tests/fixtures/GROUND_FLOOR.pdf",
            furniture_images=[],
            brief_data=None,
        )

        assert result.confidence_overall == 0.0


@pytest.mark.asyncio
async def test_extraction_result_model_validation():
    """Test that ExtractionResult model validates correctly."""
    result = ExtractionResult(
        project_id="test_001",
        rooms=[
            RoomGeometryExtracted(
                id="room_001",
                label="Sales Lounge",
                polygon_relative=[[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
                area_sqm_estimated=38.0,
            )
        ],
        missing_fields=[
            MissingField(
                field="ceiling_height_m",
                question="What is the ceiling height?",
                default_guess=3.0,
                importance="high",
            )
        ],
        overall_style="modern",
        lighting_cues="natural light",
        confidence_overall=0.78,
        raw_gemini_response='{"test": true}',
    )

    assert result.project_id == "test_001"
    assert len(result.rooms) == 1
    assert result.rooms[0].label == "Sales Lounge"
    assert result.confidence_overall == 0.78
