"""FurniVision AI — Agent 1: Parser — PDF to structured JSON extraction."""

import json
import logging
import uuid
from pathlib import Path

from models.extraction import (
    ExtractionResult,
    RoomGeometryExtracted,
    FurnitureItemExtracted,
    WallGeometry,
    DoorGeometry,
    WindowGeometry,
    FurnitureAssignment,
    ScaleInfo,
    MissingField,
)
from services.gemini import GeminiService
from services.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — complete extraction schema
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are FurniVision AI Agent 1 — an expert architectural floor-plan analyst and \
furniture cataloguer. You will receive:
  1. One or more rendered PNG pages of a floor-plan PDF (300 DPI).
  2. Zero or more embedded images extracted from the PDF itself.
  3. Zero or more separate furniture product images.

Your task is to extract EVERY piece of information visible in the floor plan and \
the furniture images and return a single, strict JSON object that conforms exactly \
to the schema below. Do NOT include any text outside the JSON object.

### Extraction rules
- **Rooms**: Identify every distinct room / zone. Assign each a unique id \
  (e.g. "room_01"). Provide a human-readable label ("Living Room", "Bedroom 1", \
  etc.) and the raw label as printed on the plan. Estimate the polygon as a list \
  of [x, y] coordinates normalised to 0.0–1.0 relative to the full plan extent. \
  Estimate area in square metres if any scale reference is available.
- **Walls**: List every wall segment as start/end relative coordinates. Include \
  thickness and height when visible.
- **Doors**: For every door, record the room it belongs to, its relative position, \
  estimated width, and swing direction.
- **Windows**: For every window, record the room, start/end relative coordinates, \
  and sill height if annotated.
- **Furniture assignments**: For each furniture product image (indexed from 0), \
  decide which room it most likely belongs to based on the floor plan context, \
  labels, colour cues, or layout logic. Provide a confidence score 0.0–1.0 and \
  explain the assignment_basis.
- **Furniture items**: For each furniture product image, extract the item name, \
  type (sofa, table, chair, bed, shelf, lamp, rug, desk, wardrobe, other), \
  primary and secondary colours, material, style tags, estimated dimensions \
  {h_m, w_m, d_m}, and image quality classification.
- **Scale info**: Note whether a scale bar or dimension annotations exist and \
  whether calibration is possible.
- **Missing fields**: List any information that you could NOT determine but that \
  is important for rendering (e.g. ceiling height, wall colour). Provide a \
  question for the user, a default guess, and an importance level.
- **Overall style**: Infer the interior design style from plan annotations and \
  furniture (e.g. "modern minimalist", "industrial loft", "Scandinavian").
- **Lighting cues**: Describe natural and artificial lighting hints from the plan \
  (window sizes, orientation, light fixture symbols).
- **Confidence**: Provide an overall confidence score 0.0–1.0 for the entire \
  extraction.

### Required JSON schema
```json
{
  "rooms": [
    {
      "id": "room_01",
      "label": "Living Room",
      "label_raw": "LIVING",
      "polygon_relative": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.6], [0.1, 0.6]],
      "area_sqm_estimated": 25.0,
      "position_on_plan": "bottom-left quadrant",
      "notes": ""
    }
  ],
  "walls": [
    {
      "start_relative": [0.0, 0.0],
      "end_relative": [1.0, 0.0],
      "thickness_relative": 0.01,
      "height_m": 3.0
    }
  ],
  "doors": [
    {
      "room_id": "room_01",
      "position_relative": [0.3, 0.1],
      "width_m_estimated": 0.9,
      "swing_direction": "inward-left"
    }
  ],
  "windows": [
    {
      "room_id": "room_01",
      "start_relative": [0.5, 0.2],
      "end_relative": [0.5, 0.4],
      "sill_height_m": 0.9
    }
  ],
  "furniture_assignments": [
    {
      "furniture_image_index": 0,
      "room_id": "room_01",
      "item_name": "Grey L-shaped Sofa",
      "confidence": 0.85,
      "assignment_basis": "Sofa fits living room area and matches modern style"
    }
  ],
  "furniture_items": [
    {
      "furniture_image_index": 0,
      "item_name": "Grey L-shaped Sofa",
      "item_type": "sofa",
      "color_primary": "charcoal grey",
      "color_secondary": "silver legs",
      "material": "fabric upholstery",
      "style_tags": ["modern", "minimalist"],
      "dims_estimated": {"h_m": 0.85, "w_m": 2.8, "d_m": 1.6},
      "image_quality": "product_render",
      "notes": ""
    }
  ],
  "scale_info": {
    "has_scale_bar": false,
    "has_dimension_annotations": true,
    "reference_dimension_found": "4200mm wall segment",
    "calibration_possible": true,
    "notes": ""
  },
  "missing_fields": [
    {
      "field": "ceiling_height_m",
      "question": "What is the ceiling height?",
      "default_guess": 2.7,
      "importance": "high"
    }
  ],
  "overall_style": "modern minimalist",
  "lighting_cues": "Large south-facing windows suggest strong natural daylight; recessed ceiling light symbols in kitchen.",
  "confidence_overall": 0.82
}
```

Return ONLY the JSON object. No markdown fences, no commentary.
"""

EXTRACTION_USER_PROMPT = """\
Analyse the attached floor-plan pages and furniture images. \
The floor-plan pages come first, followed by any embedded images from the PDF, \
then the individual furniture product images (indexed starting from 0). \
Extract all rooms, walls, doors, windows, furniture assignments, furniture item \
details, scale info, missing fields, overall style, lighting cues, and confidence. \
Return ONLY the JSON object conforming to the schema in your instructions.\
"""

RETRY_USER_PROMPT = (
    "Your previous response was not valid JSON. "
    "Return ONLY the JSON object as specified in the schema. No extra text."
)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ParserAgent:
    """Agent 1 — parses a floor-plan PDF and furniture images into structured data."""

    def __init__(self) -> None:
        self.gemini = GeminiService()
        self.pdf_processor = PDFProcessor()

    async def parse(
        self,
        pdf_path: str,
        furniture_images: list[dict],
        brief_data: dict | None = None,
    ) -> ExtractionResult:
        """Run the full extraction pipeline.

        Parameters
        ----------
        pdf_path:
            Local path to the floor-plan PDF.
        furniture_images:
            List of dicts with at least ``{"path": str}`` (local file path)
            and optionally ``{"id": str, "filename": str}``.
        brief_data:
            Optional dict of project brief overrides.

        Returns
        -------
        ExtractionResult
        """
        project_id = (brief_data or {}).get("project_id", str(uuid.uuid4()))
        logger.info(
            "ParserAgent.parse started — pdf=%s, furniture_count=%d, project=%s",
            pdf_path, len(furniture_images), project_id,
        )

        # ------------------------------------------------------------------
        # 1. Convert PDF pages to PNG at 300 DPI
        # ------------------------------------------------------------------
        logger.info("Step 1: Converting PDF to page images at 300 DPI")
        page_images: list[bytes] = self.pdf_processor.convert_to_images(pdf_path, dpi=300)
        logger.info("Rendered %d page image(s)", len(page_images))

        # ------------------------------------------------------------------
        # 2. Extract embedded images from the PDF
        # ------------------------------------------------------------------
        logger.info("Step 2: Extracting embedded images from PDF")
        embedded_images: list[bytes] = self.pdf_processor.extract_embedded_images(pdf_path)
        logger.info("Extracted %d embedded image(s)", len(embedded_images))

        # ------------------------------------------------------------------
        # 3. Load furniture images as bytes
        # ------------------------------------------------------------------
        logger.info("Step 3: Loading %d furniture image(s)", len(furniture_images))
        furniture_bytes: list[bytes] = []
        for fi in furniture_images:
            fpath = fi.get("path", "")
            try:
                data = Path(fpath).read_bytes()
                furniture_bytes.append(data)
                logger.debug("Loaded furniture image: %s (%d bytes)", fpath, len(data))
            except Exception:
                logger.warning("Could not read furniture image at %s — skipping", fpath)

        # ------------------------------------------------------------------
        # 4. Build combined image list for Gemini
        # ------------------------------------------------------------------
        all_images: list[bytes] = page_images + embedded_images + furniture_bytes
        logger.info(
            "Total images for Gemini: %d (pages=%d, embedded=%d, furniture=%d)",
            len(all_images), len(page_images), len(embedded_images), len(furniture_bytes),
        )

        # Augment user prompt with brief data if provided
        user_prompt = EXTRACTION_USER_PROMPT
        if brief_data:
            brief_str = "\n\nAdditional project brief context:\n"
            for k, v in brief_data.items():
                if k != "project_id":
                    brief_str += f"  - {k}: {v}\n"
            user_prompt += brief_str

        # ------------------------------------------------------------------
        # 5. Call Gemini with all images
        # ------------------------------------------------------------------
        logger.info("Step 5: Calling Gemini for structured extraction")
        raw_response_text = ""
        parsed: dict | None = None

        try:
            parsed = await self.gemini.analyze_images_structured(
                images=all_images,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_retries=1,
            )
            raw_response_text = str(parsed)
            logger.info("Gemini extraction succeeded on first call")
        except Exception as first_err:
            logger.warning("First Gemini call failed: %s — retrying with nudge", first_err)

            # ------------------------------------------------------------------
            # 7. Retry once with a corrective prompt
            # ------------------------------------------------------------------
            try:
                parsed = await self.gemini.analyze_images_structured(
                    images=all_images,
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=RETRY_USER_PROMPT,
                    max_retries=1,
                )
                raw_response_text = str(parsed)
                logger.info("Gemini extraction succeeded on retry")
            except Exception as retry_err:
                # ------------------------------------------------------------------
                # 8. On retry fail — return partial result
                # ------------------------------------------------------------------
                logger.error("Gemini retry also failed: %s — returning partial result", retry_err)
                return ExtractionResult(
                    project_id=project_id,
                    confidence_overall=0.0,
                    raw_gemini_response=f"FIRST_ERROR: {first_err} | RETRY_ERROR: {retry_err}",
                )

        # ------------------------------------------------------------------
        # 6. Parse response into ExtractionResult
        # ------------------------------------------------------------------
        logger.info("Step 6: Parsing Gemini response into ExtractionResult")
        return self._build_extraction_result(parsed, project_id, raw_response_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_extraction_result(
        self, data: dict, project_id: str, raw_response: str
    ) -> ExtractionResult:
        """Convert a raw Gemini JSON dict into a validated ExtractionResult."""

        rooms = [
            RoomGeometryExtracted(**r) for r in data.get("rooms", [])
        ]
        walls = [
            WallGeometry(**w) for w in data.get("walls", [])
        ]
        doors = [
            DoorGeometry(**d) for d in data.get("doors", [])
        ]
        windows = [
            WindowGeometry(**w) for w in data.get("windows", [])
        ]
        furniture_assignments = [
            FurnitureAssignment(**fa) for fa in data.get("furniture_assignments", [])
        ]
        furniture_items = [
            FurnitureItemExtracted(**fi) for fi in data.get("furniture_items", [])
        ]

        scale_raw = data.get("scale_info", {})
        scale_info = ScaleInfo(**scale_raw) if scale_raw else ScaleInfo()

        missing_fields = [
            MissingField(**mf) for mf in data.get("missing_fields", [])
        ]

        overall_style = data.get("overall_style", "")
        lighting_cues = data.get("lighting_cues", "")
        confidence_overall = float(data.get("confidence_overall", 0.0))

        result = ExtractionResult(
            project_id=project_id,
            rooms=rooms,
            walls=walls,
            doors=doors,
            windows=windows,
            furniture_assignments=furniture_assignments,
            furniture_items=furniture_items,
            scale_info=scale_info,
            missing_fields=missing_fields,
            overall_style=overall_style,
            lighting_cues=lighting_cues,
            confidence_overall=confidence_overall,
            raw_gemini_response=raw_response,
        )

        logger.info(
            "ExtractionResult built: %d rooms, %d walls, %d doors, %d windows, "
            "%d assignments, %d items, confidence=%.2f",
            len(rooms), len(walls), len(doors), len(windows),
            len(furniture_assignments), len(furniture_items), confidence_overall,
        )
        return result
