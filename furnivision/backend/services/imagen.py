"""FurniVision AI — Imagen 3 image-generation service."""

import asyncio
import logging

import google.generativeai as genai

from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom error
# ---------------------------------------------------------------------------


class ImagenError(Exception):
    """Raised when Imagen 3 image generation fails."""


# ---------------------------------------------------------------------------
# Default negative prompt
# ---------------------------------------------------------------------------

_DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, deformed, watermark, text overlay, "
    "cartoon, anime, sketch, out of frame, cropped, bad anatomy, "
    "extra limbs, ugly, duplicate, morbid, mutilated"
)

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ImagenService:
    """Wrapper around the Imagen 3 image-generation API."""

    def __init__(self) -> None:
        genai.configure(api_key=GOOGLE_API_KEY)
        self._model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        logger.info("ImagenService initialised (model=imagen-3.0-generate-002)")

    # ------------------------------------------------------------------
    # Single generation
    # ------------------------------------------------------------------

    async def generate_frame(
        self,
        prompt: str,
        negative_prompt: str = _DEFAULT_NEGATIVE_PROMPT,
        width: int = 1536,
        height: int = 1024,
        seed: int | None = None,
    ) -> bytes:
        """Generate a single image via Imagen 3 and return PNG bytes.

        Raises :class:`ImagenError` on any failure.
        """
        loop = asyncio.get_running_loop()

        generation_config: dict = {
            "number_of_images": 1,
            "aspect_ratio": self._aspect_ratio(width, height),
            "negative_prompt": negative_prompt,
        }
        if seed is not None:
            generation_config["seed"] = seed

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_images(
                    prompt=prompt,
                    **generation_config,
                ),
            )

            if not response.images:
                raise ImagenError("Imagen returned no images")

            image = response.images[0]
            # The SDK image object exposes ._image_bytes or .image_bytes
            image_bytes: bytes = getattr(
                image, "_image_bytes", getattr(image, "image_bytes", None)
            )
            if image_bytes is None:
                # Fallback: convert PIL image to bytes
                import io
                buf = io.BytesIO()
                image._pil_image.save(buf, format="PNG")
                image_bytes = buf.getvalue()

            logger.info(
                "Imagen generated %d bytes (prompt=%.80s...)", len(image_bytes), prompt
            )
            return image_bytes

        except ImagenError:
            raise
        except Exception as exc:
            logger.exception("Imagen generation failed: %s", exc)
            raise ImagenError(f"Imagen generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Generation with retry
    # ------------------------------------------------------------------

    async def generate_frame_with_retry(
        self,
        prompt: str,
        negative_prompt: str = _DEFAULT_NEGATIVE_PROMPT,
        width: int = 1536,
        height: int = 1024,
        seed: int | None = None,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> bytes:
        """Call :meth:`generate_frame` with exponential back-off retries.

        Raises :class:`ImagenError` if all attempts are exhausted.
        """
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                return await self.generate_frame(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    seed=seed,
                )
            except Exception as exc:
                last_error = exc
                wait = backoff_base ** attempt
                logger.warning(
                    "Imagen attempt %d/%d failed (%s). Retrying in %.1fs...",
                    attempt, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)

        raise ImagenError(
            f"Imagen generation failed after {max_retries} retries"
        ) from last_error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> str:
        """Convert pixel dimensions to the closest Imagen aspect-ratio string."""
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
            return "3:2"
        else:
            return "2:3"
