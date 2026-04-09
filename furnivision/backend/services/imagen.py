"""FurniVision AI — Image generation service.

Two modes:
  - generate_frame(prompt)               → Imagen 4 text-to-image (no reference)
  - generate_frame_from_reference(...)   → Gemini Flash Image (image-to-image)
    Passes the reference render as visual context so the output matches
    the actual room dimensions, furniture, and materials.
"""

import asyncio
import base64
import logging

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

_IMAGEN_MODEL = "imagen-4.0-fast-generate-001"
_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"


class ImagenError(Exception):
    """Raised when image generation fails."""


class ImagenService:
    """Wrapper around Imagen 4 (text→image) and Gemini Flash Image (ref→image)."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info(
            "ImagenService initialised (imagen=%s, gemini_img=%s)",
            _IMAGEN_MODEL, _GEMINI_IMAGE_MODEL,
        )

    # ------------------------------------------------------------------
    # Primary: reference-image-based generation (Gemini Flash Image)
    # ------------------------------------------------------------------

    async def generate_frame_from_reference(
        self,
        prompt: str,
        reference_image: bytes,
        reference_mime: str = "image/jpeg",
    ) -> bytes:
        """Generate a frame using a reference image as visual context.

        Uses Gemini Flash Image which accepts an existing room render and
        produces a new frame matching the same room — same furniture,
        proportions, colors, materials, lighting.

        Returns PNG bytes.
        """
        loop = asyncio.get_running_loop()

        logger.info(
            "Gemini image-from-reference — ref=%d bytes, prompt=%.80s...",
            len(reference_image), prompt,
        )

        ref_data = base64.b64encode(reference_image).decode()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=_GEMINI_IMAGE_MODEL,
                    contents=[
                        {"inline_data": {"mime_type": reference_mime, "data": ref_data}},
                        {"text": prompt},
                    ],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                ),
            )

            for part in response.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline:
                    raw = inline.data
                    img_bytes = (
                        base64.b64decode(raw) if isinstance(raw, str) else raw
                    )
                    logger.info(
                        "Gemini image-from-reference succeeded: %d bytes", len(img_bytes)
                    )
                    return img_bytes

            raise ImagenError("Gemini Flash Image returned no image data")

        except ImagenError:
            raise
        except Exception as exc:
            logger.exception("Gemini image-from-reference failed: %s", exc)
            raise ImagenError(f"Gemini image-from-reference failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Fallback: text-to-image (Imagen 4)
    # ------------------------------------------------------------------

    async def generate_frame(
        self,
        prompt: str,
        width: int = 1536,
        height: int = 1024,
        seed: int | None = None,
    ) -> bytes:
        """Generate a single image via Imagen 4 (text only, no reference).

        Raises :class:`ImagenError` on any failure.
        """
        loop = asyncio.get_running_loop()

        config_kwargs: dict = {
            "number_of_images": 1,
            "aspect_ratio": self._aspect_ratio(width, height),
        }
        if seed is not None:
            config_kwargs["seed"] = seed

        generation_config = types.GenerateImagesConfig(**config_kwargs)

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_images(
                    model=_IMAGEN_MODEL,
                    prompt=prompt,
                    config=generation_config,
                ),
            )

            if not response.generated_images:
                raise ImagenError("Imagen returned no images")

            image = response.generated_images[0].image
            image_bytes: bytes | None = getattr(image, "image_bytes", None)
            if not image_bytes:
                raise ImagenError("Imagen image has no bytes")

            logger.info(
                "Imagen 4 generated %d bytes (prompt=%.80s...)", len(image_bytes), prompt
            )
            return image_bytes

        except ImagenError:
            raise
        except Exception as exc:
            logger.exception("Imagen generation failed: %s", exc)
            raise ImagenError(f"Imagen generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Retry wrappers
    # ------------------------------------------------------------------

    async def generate_frame_with_retry(
        self,
        prompt: str,
        reference_image: bytes | None = None,
        reference_mime: str = "image/jpeg",
        width: int = 1536,
        height: int = 1024,
        seed: int | None = None,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> bytes:
        """Generate with retries. Uses reference if provided, Imagen 4 otherwise."""
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                if reference_image:
                    return await self.generate_frame_from_reference(
                        prompt=prompt,
                        reference_image=reference_image,
                        reference_mime=reference_mime,
                    )
                else:
                    return await self.generate_frame(
                        prompt=prompt,
                        width=width,
                        height=height,
                        seed=seed,
                    )
            except Exception as exc:
                last_error = exc
                wait = min(backoff_base ** attempt, 30)
                logger.warning(
                    "Image gen attempt %d/%d failed (%s). Retrying in %.1fs...",
                    attempt, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)

        raise ImagenError(
            f"Image generation failed after {max_retries} retries"
        ) from last_error

    # ------------------------------------------------------------------
    # Multi-reference refinement (Gemini Flash Image with multiple refs)
    # ------------------------------------------------------------------

    async def generate_frame_from_reference_multi(
        self,
        prompt: str,
        base_image: bytes,
        reference_images: list[bytes],
        base_mime: str = "image/png",
        ref_mime: str = "image/png",
    ) -> bytes:
        """Refine a base render using multiple product reference images.

        Sends the base room render + up to 5 product images as inline_data
        to Gemini Flash Image, which produces a refined render incorporating
        the exact products.

        Returns PNG bytes.
        """
        loop = asyncio.get_running_loop()

        logger.info(
            "Gemini multi-ref refinement — base=%d bytes, refs=%d, prompt=%.80s...",
            len(base_image), len(reference_images), prompt,
        )

        # Build content parts: base image + reference images + prompt
        contents = []
        contents.append({
            "inline_data": {
                "mime_type": base_mime,
                "data": base64.b64encode(base_image).decode(),
            }
        })
        for ref_img in reference_images[:5]:
            contents.append({
                "inline_data": {
                    "mime_type": ref_mime,
                    "data": base64.b64encode(ref_img).decode(),
                }
            })
        contents.append({"text": prompt})

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=_GEMINI_IMAGE_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                ),
            )

            for part in response.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline:
                    raw = inline.data
                    img_bytes = (
                        base64.b64decode(raw) if isinstance(raw, str) else raw
                    )
                    logger.info(
                        "Gemini multi-ref refinement succeeded: %d bytes", len(img_bytes)
                    )
                    return img_bytes

            raise ImagenError("Gemini Flash Image multi-ref returned no image data")

        except ImagenError:
            raise
        except Exception as exc:
            logger.exception("Gemini multi-ref refinement failed: %s", exc)
            raise ImagenError(f"Gemini multi-ref refinement failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Targeted image edit (for feedback loop)
    # ------------------------------------------------------------------

    async def edit_image_with_feedback(
        self,
        current_image: bytes,
        feedback: str,
        reference_images: list[bytes] | None = None,
        current_mime: str = "image/png",
        region: dict | None = None,
    ) -> bytes:
        """Edit an existing room render based on text feedback.

        Optionally includes product reference images for context.
        Uses Gemini Flash Image to apply targeted edits.

        Parameters
        ----------
        region : dict | None
            Optional region to constrain the edit. Format:
            {"x": 0.0-1.0, "y": 0.0-1.0, "width": 0.0-1.0, "height": 0.0-1.0}
            Values are relative to image dimensions.

        Returns PNG bytes.
        """
        loop = asyncio.get_running_loop()

        logger.info(
            "Gemini image edit — image=%d bytes, feedback=%.100s..., refs=%d, region=%s",
            len(current_image), feedback, len(reference_images or []), region,
        )

        contents = []
        contents.append({
            "inline_data": {
                "mime_type": current_mime,
                "data": base64.b64encode(current_image).decode(),
            }
        })

        if reference_images:
            for ref in reference_images[:3]:
                contents.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(ref).decode(),
                    }
                })

        # Build region description for the prompt
        region_desc = ""
        if region:
            x, y = region.get("x", 0), region.get("y", 0)
            w, h = region.get("width", 1), region.get("height", 1)
            cx, cy = x + w / 2, y + h / 2
            # Describe position in natural language
            v_pos = "top" if cy < 0.33 else "bottom" if cy > 0.66 else "middle"
            h_pos = "left" if cx < 0.33 else "right" if cx > 0.66 else "center"
            region_desc = (
                f"\n\nREGION: Focus ONLY on the {v_pos}-{h_pos} area of the image "
                f"(approximately {int(x*100)}%-{int((x+w)*100)}% from left, "
                f"{int(y*100)}%-{int((y+h)*100)}% from top). "
                f"Do NOT modify anything outside this region."
            )

        edit_prompt = (
            f"Edit this room render based on the following feedback:\n\n"
            f"FEEDBACK: {feedback}{region_desc}\n\n"
            f"INSTRUCTIONS:\n"
            f"- Apply ONLY the changes described in the feedback\n"
            f"- Keep everything else exactly the same (camera angle, lighting, layout)\n"
            f"- If reference product images are provided, use them to match exact colors/shapes\n"
            f"- Maintain photorealistic quality\n"
            f"- Output the edited image"
        )
        contents.append({"text": edit_prompt})

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=_GEMINI_IMAGE_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                ),
            )

            for part in response.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline:
                    raw = inline.data
                    img_bytes = (
                        base64.b64decode(raw) if isinstance(raw, str) else raw
                    )
                    logger.info("Gemini image edit succeeded: %d bytes", len(img_bytes))
                    return img_bytes

            raise ImagenError("Gemini Flash Image edit returned no image data")

        except ImagenError:
            raise
        except Exception as exc:
            logger.exception("Gemini image edit failed: %s", exc)
            raise ImagenError(f"Gemini image edit failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> str:
        ratio = width / height
        if abs(ratio - 1.0) < 0.1:
            return "1:1"
        elif abs(ratio - 16 / 9) < 0.15:
            return "16:9"
        elif abs(ratio - 9 / 16) < 0.15:
            return "9:16"
        elif abs(ratio - 4 / 3) < 0.15:
            return "4:3"
        elif abs(ratio - 3 / 4) < 0.15:
            return "3:4"
        elif ratio > 1:
            return "16:9"
        else:
            return "9:16"
