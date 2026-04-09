"""FurniVision AI — Gemini API service (vision + text)."""

import asyncio
import json
import logging
import re

import google.generativeai as genai
from google.generativeai.types import ContentDict

from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from *text*, stripping optional markdown fences."""
    # Try the raw text first
    text_stripped = text.strip()
    if text_stripped.startswith("{"):
        return json.loads(text_stripped)
    # Try to pull from a code fence
    match = _JSON_FENCE_RE.search(text)
    if match:
        return json.loads(match.group(1).strip())
    # Last resort — find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("No JSON object found in response", text, 0)


def _image_part(image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """Build an inline image part for the Gemini API."""
    return {"inline_data": {"mime_type": mime_type, "data": image_bytes}}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GeminiService:
    """High-level wrapper around the Gemini 2.5 Pro model."""

    def __init__(self) -> None:
        genai.configure(api_key=GOOGLE_API_KEY)
        self._model = genai.GenerativeModel("gemini-2.5-pro")
        logger.info("GeminiService initialised (model=gemini-2.5-pro)")

    # ------------------------------------------------------------------
    # Generic structured vision call
    # ------------------------------------------------------------------

    async def analyze_images_structured(
        self,
        images: list[bytes],
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> dict:
        """Send one or more images to Gemini Vision, parse a JSON response.

        Retries up to *max_retries* times when the response is not valid JSON.
        """
        parts: list = [{"text": system_prompt}]
        for img in images:
            parts.append(_image_part(img))
        parts.append({"text": user_prompt})

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._model.generate_content(parts),
                )
                raw_text = response.text
                logger.info(
                    "Gemini raw response (attempt %d, len=%d): %s",
                    attempt, len(raw_text), raw_text[:500],
                )
                result = _extract_json(raw_text)
                return result
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning(
                    "JSON parse failed on attempt %d/%d: %s",
                    attempt, max_retries, exc,
                )
            except Exception as exc:
                last_error = exc
                logger.exception("Gemini call failed on attempt %d/%d", attempt, max_retries)

        raise RuntimeError(
            f"Failed to get valid JSON from Gemini after {max_retries} attempts"
        ) from last_error

    # ------------------------------------------------------------------
    # Pairwise consistency check
    # ------------------------------------------------------------------

    async def compare_frame_pair(self, frame_a: bytes, frame_b: bytes) -> dict:
        """Compare two frames for visual consistency.

        Returns ``{"score": float, "issues": [str, ...]}``.
        """
        system_prompt = (
            "You are a visual-consistency QC agent. You will receive two interior-design "
            "frames that should depict the same room from slightly different angles. "
            "Score their consistency from 0.0 (completely different) to 1.0 (perfectly "
            "consistent). List any issues you find."
        )
        user_prompt = (
            "Compare these two frames. Respond ONLY with a JSON object:\n"
            '{"score": <float 0-1>, "issues": ["issue1", ...]}\n'
            "No extra text."
        )
        return await self.analyze_images_structured(
            images=[frame_a, frame_b],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    # ------------------------------------------------------------------
    # Hero frame selection
    # ------------------------------------------------------------------

    async def select_hero_frames(self, keyframes: list[bytes]) -> dict:
        """Pick the best 5 hero frames from a list of keyframe images.

        Returns ``{"selected": [int, ...], "reasoning": str}``.
        """
        system_prompt = (
            "You are a creative director reviewing a set of interior-design keyframes "
            "for a room. Select the 5 best frames that together tell a compelling visual "
            "story — consider composition, lighting, and variety of angle."
        )
        user_prompt = (
            f"You are given {len(keyframes)} keyframes (indexed 0..{len(keyframes) - 1}). "
            "Pick the 5 best. Respond ONLY with JSON:\n"
            '{"selected": [idx, ...], "reasoning": "..."}\n'
            "No extra text."
        )
        return await self.analyze_images_structured(
            images=keyframes,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    # ------------------------------------------------------------------
    # Rejection feedback interpretation
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Scene composition: floor plan + furniture catalogue → room description
    # ------------------------------------------------------------------

    async def compose_room_scene(
        self,
        floor_plan_bytes: bytes,
        furniture_images: list[bytes],
        room_label: str,
        style_context: str = "",
    ) -> str:
        """Analyse a floor plan + per-room furniture catalogue images.

        Returns a detailed free-text Imagen prompt describing the room with
        exact furniture colours, materials, and placement positions inferred
        from the floor plan layout.

        Accepts up to 7 images: 1 floor plan + up to 6 furniture catalogue shots.
        """
        parts: list = [_image_part(floor_plan_bytes)]
        for img_bytes in furniture_images[:6]:
            parts.append(_image_part(img_bytes))

        furniture_count = min(len(furniture_images), 6)
        user_text = (
            f"You are looking at:\n"
            f"1. IMAGE 1 — a floor plan (top-down CAD view) of a commercial space. "
            f"Find the '{room_label}' zone on this plan.\n"
            f"2. IMAGES 2–{furniture_count + 1} — the EXACT furniture pieces assigned "
            f"to the '{room_label}' room (product catalogue renders on white background).\n\n"
            f"Use scale cues visible in the floor plan (standard door width ≈ 90 cm, "
            f"desk ≈ 160 cm wide) to estimate the room's dimensions.\n\n"
            f"Style context: {style_context or 'modern commercial interior'}\n\n"
            f"Write a DETAILED PHOTOREALISTIC IMAGEN PROMPT (300-500 words) describing this "
            f"room as it would appear in a high-quality 3D render. Include:\n"
            f"• Room dimensions (width × depth × ceiling height estimated from the plan)\n"
            f"• Floor material and colour (infer from style context)\n"
            f"• Wall finish and colour\n"
            f"• Every furniture piece shown in the catalogue images — EXACT colour, material, "
            f"fabric texture, metal finish, and its position/orientation in the room as laid "
            f"out on the floor plan\n"
            f"• Natural light sources (window positions from plan) and artificial lighting\n"
            f"• Camera: wide-angle entrance shot showing the full room\n\n"
            f"Start the prompt with: "
            f"'Photorealistic architectural interior render of a {room_label}, ...'\n"
            f"Be extremely specific about furniture details — reference what you see in "
            f"the catalogue images (e.g. 'terracotta boucle armchair with copper sled legs')."
        )
        parts.append({"text": user_text})

        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._model.generate_content(parts),
                )
                text = response.text.strip()
                logger.info(
                    "compose_room_scene '%s' attempt %d — %d chars",
                    room_label, attempt, len(text),
                )
                return text
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "compose_room_scene attempt %d failed for '%s': %s",
                    attempt, room_label, exc,
                )

        logger.warning("Falling back to generic description for '%s'", room_label)
        return (
            f"Photorealistic architectural interior render of a {room_label}. "
            f"{style_context or 'Modern commercial interior, contemporary design'}. "
            "Professional furniture arrangement with high-quality pieces, "
            "warm natural lighting from windows, detailed textures and materials, "
            "wide-angle shot showing the full room, no people, 4K quality."
        )

    async def interpret_rejection_feedback(
        self, feedback: str, scene_plan: dict
    ) -> dict:
        """Interpret human rejection feedback and suggest prompt adjustments.

        Returns ``{"prompt_adjustments": dict, "affected_frames": [int, ...]}``.
        """
        system_prompt = (
            "You are a prompt-engineering assistant for an AI interior-design pipeline. "
            "Given human rejection feedback and the original scene plan, determine which "
            "prompts need adjustment and which frames are affected."
        )
        user_prompt = (
            f"Rejection feedback: {feedback}\n\n"
            f"Scene plan: {json.dumps(scene_plan, indent=2)}\n\n"
            "Respond ONLY with JSON:\n"
            '{"prompt_adjustments": {<key>: <new_value>, ...}, '
            '"affected_frames": [int, ...]}\n'
            "No extra text."
        )
        # No images for this call
        parts: list = [{"text": system_prompt}, {"text": user_prompt}]

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._model.generate_content(parts),
                )
                raw_text = response.text
                logger.info(
                    "Gemini rejection-interpretation raw (attempt %d): %s",
                    attempt, raw_text[:500],
                )
                return _extract_json(raw_text)
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning("JSON parse failed attempt %d: %s", attempt, exc)
            except Exception as exc:
                last_error = exc
                logger.exception("Gemini call failed attempt %d", attempt)

        raise RuntimeError(
            "Failed to interpret rejection feedback after 3 attempts"
        ) from last_error
