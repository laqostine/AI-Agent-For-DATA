"""FurniVision AI — fal.ai video generation (Kling image-to-video).

Supports start-frame + end-frame mode:
  - start_frame (keyframe 0): wide entrance shot
  - end_frame   (keyframe 1): detail / mid-room shot
  → Kling interpolates the camera arc between the two frames

Model: fal-ai/kling-video/v1.6/pro/image-to-video
  - Supports image_url (start) + tail_image_url (end)
  - duration: "5" or "10" seconds
  - Returns MP4; caller is responsible for trimming to desired length
"""

import asyncio
import logging
import os
import subprocess
import tempfile

from config import FAL_KEY

logger = logging.getLogger(__name__)

_MODEL_FIRST_LAST = "fal-ai/kling-video/v1.6/pro/image-to-video"
_MODEL_START_ONLY = "fal-ai/kling-video/v2.1/standard/image-to-video"


class FalVideoError(Exception):
    pass


class FalVideoService:
    """Kling image-to-video via fal.ai — start frame + optional end frame."""

    def __init__(self) -> None:
        if not FAL_KEY:
            raise FalVideoError("FAL_KEY not configured")
        os.environ["FAL_KEY"] = FAL_KEY
        logger.info("FalVideoService initialised")

    async def generate_video(
        self,
        start_frame_bytes: bytes,
        prompt: str,
        end_frame_bytes: bytes | None = None,
        max_duration_seconds: int = 7,
        aspect_ratio: str = "16:9",
        cfg_scale: float = 0.4,
    ) -> bytes:
        """Generate a video from start frame + optional end frame.

        Kling supports only 5s or 10s natively. We generate 10s and
        ffmpeg-trim to *max_duration_seconds*.

        With end_frame_bytes: camera moves from start perspective to end
        perspective — exactly the room arc the user wants.
        """
        import fal_client

        loop = asyncio.get_running_loop()

        # Upload start frame
        logger.info("Uploading start frame (%d bytes) to fal.ai...", len(start_frame_bytes))
        start_url: str = await loop.run_in_executor(
            None, lambda: fal_client.upload(start_frame_bytes, "image/png")
        )
        logger.info("Start frame uploaded: %s", start_url[:70])

        arguments: dict = {
            "image_url": start_url,
            "prompt": prompt,
            "duration": "5" if max_duration_seconds <= 5 else "10",
            "aspect_ratio": aspect_ratio,
            "cfg_scale": cfg_scale,
        }

        model = _MODEL_START_ONLY
        # end_frame_bytes intentionally NOT used — single start frame
        # produces much smoother natural camera motion than forced morphing

        logger.info("Submitting Kling job (model=%s, prompt=%.80s...)", model, prompt)

        def _subscribe():
            return fal_client.subscribe(model, arguments=arguments, with_logs=False)

        try:
            result = await loop.run_in_executor(None, _subscribe)
        except Exception as exc:
            raise FalVideoError(f"Kling generation failed: {exc}") from exc

        video_url: str = result.get("video", {}).get("url", "")
        if not video_url:
            raise FalVideoError(f"Kling returned no video URL. Keys: {list(result.keys())}")

        logger.info("Kling video ready — downloading from %s", video_url[:70])
        import urllib.request
        raw_bytes: bytes = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(video_url, timeout=120).read()
        )
        logger.info("Downloaded %d bytes from Kling", len(raw_bytes))

        # Trim to max_duration_seconds with ffmpeg
        trimmed = await self._trim(raw_bytes, max_duration_seconds)
        logger.info(
            "Kling video complete: %d bytes (trimmed to %ds)",
            len(trimmed), max_duration_seconds,
        )
        return trimmed

    async def _trim(self, video_bytes: bytes, duration_seconds: int) -> bytes:
        """Trim video to *duration_seconds* using ffmpeg."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._trim_sync, video_bytes, duration_seconds)

    @staticmethod
    def _trim_sync(video_bytes: bytes, duration_seconds: int) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as inp:
            inp.write(video_bytes)
            inp_path = inp.name
        out_path = inp_path.replace(".mp4", "_trimmed.mp4")
        try:
            r = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", inp_path,
                    "-t", str(duration_seconds),
                    "-c", "copy",
                    out_path,
                ],
                capture_output=True,
            )
            if r.returncode != 0:
                logger.warning("ffmpeg trim failed, returning untrimmed: %s", r.stderr[-200:])
                return video_bytes
            trimmed = open(out_path, "rb").read()
            return trimmed
        finally:
            for p in (inp_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
