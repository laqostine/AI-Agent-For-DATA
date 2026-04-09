"""FurniVision AI — Agent 2.5: Scene Composer (V5 Pipeline).

V4/V5 image pipeline:
  1. Imagen 4 → 16:9 base render (1536x864) from room description
  2. Gemini Flash Image → multi-ref refinement with product images (3 attempts)
  3. Best-of-3 selection via Gemini scoring

Given:
  - Floor plan PNG bytes
  - Per-room product catalogue images (clean renders)
  - Room label and style context

Produces:
  - Detailed scene description (Gemini multi-image analysis)
  - Base render (Imagen 4, 16:9)
  - Refined render (Gemini Flash Image with product refs, best of 3)
"""

import asyncio
import base64
import io
import json
import logging

from PIL import Image

from services.gemini import GeminiService
from services.imagen import ImagenService

logger = logging.getLogger(__name__)


class ComposedScene:
    """Result of Scene Composer."""

    def __init__(
        self,
        room_id: str,
        room_label: str,
        description: str,
        base_render: bytes,
        refined_render: bytes,
        refinement_attempts: int = 0,
    ) -> None:
        self.room_id = room_id
        self.room_label = room_label
        self.description = description
        self.base_render = base_render        # Imagen 4 base (16:9)
        self.refined_render = refined_render  # Best Gemini Flash Image refinement
        # Legacy alias for backward compat with orchestrator
        self.reference_render = refined_render
        self.refinement_attempts = refinement_attempts


class SceneComposerAgent:
    """Agent 2.5 — V4/V5 pipeline: Imagen base → Gemini multi-ref refinement."""

    def __init__(self) -> None:
        self.gemini = GeminiService()
        self.imagen = ImagenService()

    async def compose(
        self,
        room_id: str,
        room_label: str,
        floor_plan_bytes: bytes,
        furniture_images: list[bytes],
        scene_plan=None,
    ) -> ComposedScene:
        """Generate a refined room render using the V4/V5 pipeline.

        Steps
        -----
        1. Gemini 2.5 Pro: floor plan + furniture images → detailed scene description
        2. Imagen 4: text-to-image 16:9 base render (1536x864)
        3. Gemini Flash Image: refine base with product images as inline_data
           (3 attempts, pick best via Gemini scoring)
        """
        logger.info(
            "SceneComposerAgent.compose — room=%s (%s), furniture_images=%d",
            room_id, room_label, len(furniture_images),
        )

        style_context = ""
        if scene_plan:
            style_context = getattr(scene_plan, "style_anchor", "")[:300]

        # --- Step 1: Gemini scene description ---
        description = await self.gemini.compose_room_scene(
            floor_plan_bytes=floor_plan_bytes,
            furniture_images=furniture_images,
            room_label=room_label,
            style_context=style_context,
        )
        logger.info(
            "Gemini description for '%s' (%d chars): %.250s...",
            room_label, len(description), description,
        )

        # --- Step 2: Imagen 4 base render (16:9) ---
        base_prompt = description[:1800]
        if "photorealistic" not in base_prompt.lower():
            base_prompt = "Photorealistic architectural interior render. " + base_prompt
        base_prompt += (
            " Wide-angle shot from the entrance showing the complete room. "
            "Professional architectural visualization, 4K quality, "
            "warm natural lighting, detailed shadows, no people. "
            "16:9 aspect ratio, 1536x864 resolution."
        )

        logger.info("Step 2: Generating Imagen 4 base render for '%s'...", room_label)
        base_render = await self.imagen.generate_frame_with_retry(
            prompt=base_prompt,
            reference_image=None,   # text-to-image
            width=1536,
            height=864,             # 16:9
            max_retries=2,
        )
        logger.info("Base render ready — '%s': %d bytes", room_label, len(base_render))

        # Ensure base is 1536x864
        base_render = self._ensure_16x9(base_render)

        # --- Step 3: Gemini Flash Image multi-ref refinement (best of 3) ---
        logger.info(
            "Step 3: Gemini Flash Image refinement for '%s' (3 attempts, %d product refs)...",
            room_label, len(furniture_images),
        )

        refinement_prompt = self._build_refinement_prompt(
            room_label, description, furniture_images
        )

        # Run all 3 refinements in parallel for speed
        async def _refine(attempt: int) -> bytes:
            return await self.imagen.generate_frame_from_reference_multi(
                prompt=refinement_prompt,
                base_image=base_render,
                reference_images=furniture_images[:5],
            )

        results = await asyncio.gather(
            _refine(1), _refine(2), _refine(3),
            return_exceptions=True,
        )
        candidates: list[bytes] = []
        for i, result in enumerate(results, 1):
            if isinstance(result, bytes):
                candidates.append(result)
                logger.info("Refinement %d for '%s': %d bytes", i, room_label, len(result))
            else:
                logger.warning("Refinement %d failed for '%s': %s", i, room_label, result)

        # If no refinements succeeded, use the base render
        if not candidates:
            logger.warning(
                "All refinement attempts failed for '%s', using base render",
                room_label,
            )
            return ComposedScene(
                room_id=room_id,
                room_label=room_label,
                description=description,
                base_render=base_render,
                refined_render=base_render,
                refinement_attempts=0,
            )

        # Pick the best candidate
        if len(candidates) == 1:
            best = candidates[0]
        else:
            best = await self._pick_best_candidate(
                candidates, furniture_images, room_label
            )

        logger.info(
            "Best refinement for '%s': %d bytes (from %d candidates)",
            room_label, len(best), len(candidates),
        )

        return ComposedScene(
            room_id=room_id,
            room_label=room_label,
            description=description,
            base_render=base_render,
            refined_render=best,
            refinement_attempts=len(candidates),
        )

    # ------------------------------------------------------------------
    # Refinement prompt builder
    # ------------------------------------------------------------------

    def _build_refinement_prompt(
        self, room_label: str, description: str, furniture_images: list[bytes]
    ) -> str:
        """Build a structured prompt for Gemini Flash Image refinement."""
        n_products = min(len(furniture_images), 5)
        return (
            f"You are refining an architectural interior render of a {room_label}.\n\n"
            f"ROOM DESCRIPTION:\n{description[:1000]}\n\n"
            f"INSTRUCTIONS:\n"
            f"- The first image is the base room render to refine\n"
            f"- The next {n_products} images are the EXACT furniture products to place\n"
            f"- Replace generic furniture with these specific products\n"
            f"- Match exact colors, materials, textures, and proportions\n"
            f"- Keep the room layout, lighting, and camera angle from the base render\n"
            f"- Output a photorealistic 16:9 interior visualization\n"
            f"- Ensure furniture is naturally placed (on floor, correct scale)\n"
            f"- Maintain professional architectural visualization quality"
        )

    # ------------------------------------------------------------------
    # Best-of-N selection
    # ------------------------------------------------------------------

    async def _pick_best_candidate(
        self,
        candidates: list[bytes],
        furniture_images: list[bytes],
        room_label: str,
    ) -> bytes:
        """Use Gemini to pick the best refinement candidate.

        Sends all candidates + the product reference images to Gemini,
        asks it to pick the one that best matches the products.
        """
        try:
            # Send candidates + first 2 product refs for comparison
            all_images = candidates + furniture_images[:2]

            result = await self.gemini.analyze_images_structured(
                images=all_images,
                system_prompt=(
                    "You are a quality control agent for AI-generated interior renders. "
                    "You will compare multiple room render candidates against reference "
                    "product images to pick the best match."
                ),
                user_prompt=(
                    f"You are reviewing {len(candidates)} candidate renders of a {room_label}. "
                    f"Images 1-{len(candidates)} are the candidates. "
                    f"The remaining images are reference product photos.\n\n"
                    "Pick the candidate that:\n"
                    "1. Best matches the reference products (colors, shapes, materials)\n"
                    "2. Has the most photorealistic quality\n"
                    "3. Has the best composition and lighting\n\n"
                    'Respond with JSON: {"best_index": <0-based index>, "reasoning": "..."}'
                ),
            )
            best_idx = result.get("best_index", 0)
            if 0 <= best_idx < len(candidates):
                logger.info(
                    "Gemini picked candidate %d for '%s': %s",
                    best_idx, room_label, result.get("reasoning", "")[:200],
                )
                return candidates[best_idx]
        except Exception as exc:
            logger.warning("Best-of-N selection failed: %s — using first candidate", exc)

        return candidates[0]

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_16x9(image_bytes: bytes) -> bytes:
        """Ensure image is 1536x864 (16:9). Resize/crop if needed."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.size == (1536, 864):
                return image_bytes
            # Resize to 16:9 maintaining aspect, then center crop
            target_w, target_h = 1536, 864
            target_ratio = target_w / target_h
            img_ratio = img.width / img.height
            if img_ratio > target_ratio:
                # Too wide — resize by height, crop width
                new_h = target_h
                new_w = int(img_ratio * new_h)
            else:
                # Too tall — resize by width, crop height
                new_w = target_w
                new_h = int(new_w / img_ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            img = img.crop((left, top, left + target_w, top + target_h))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
        except Exception:
            return image_bytes
