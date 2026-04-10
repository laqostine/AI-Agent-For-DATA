"""CADRE — fal.ai video generation service.

Supports two backends:
  - MiniMax Hailuo-02 (default): $0.27/video at 768P, good quality, prompt_optimizer ON
  - Kling v2.1 (premium): $0.49/video at native resolution, best quality, cfg_scale 0.4

Both are image-to-video via fal.ai's unified API.
"""

import asyncio
import logging
import os
import subprocess
import tempfile

from config import FAL_KEY

logger = logging.getLogger(__name__)

_MODEL_MINIMAX = "fal-ai/minimax/hailuo-02/standard/image-to-video"
_MODEL_KLING = "fal-ai/kling-video/v2.1/standard/image-to-video"


class FalVideoError(Exception):
    pass


class FalVideoService:
    """Image-to-video via fal.ai — MiniMax (default) or Kling (premium)."""

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
        max_duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        cfg_scale: float = 0.4,
        video_mode: str = "standard",
    ) -> bytes:
        """Generate a video from a start frame image.

        video_mode:
          - "standard": MiniMax Hailuo-02 768P, prompt_optimizer ON, ~$0.27
          - "premium":  Kling v2.1, cfg_scale 0.4, ~$0.49
        """
        import fal_client

        loop = asyncio.get_running_loop()

        # Upload start frame
        content_type = "image/png" if start_frame_bytes[:4] == b'\x89PNG' else "image/jpeg"
        logger.info("Uploading start frame (%d bytes) to fal.ai...", len(start_frame_bytes))
        start_url: str = await loop.run_in_executor(
            None, lambda: fal_client.upload(start_frame_bytes, content_type)
        )
        logger.info("Start frame uploaded: %s", start_url[:70])

        if video_mode == "premium":
            model = _MODEL_KLING
            arguments = {
                "image_url": start_url,
                "prompt": prompt,
                "duration": "5" if max_duration_seconds <= 5 else "10",
                "aspect_ratio": aspect_ratio,
                "cfg_scale": cfg_scale,
            }
        else:
            model = _MODEL_MINIMAX
            arguments = {
                "image_url": start_url,
                "prompt": prompt,
                "resolution": "768P",
                "duration": 6,
                "prompt_optimizer": True,
            }

        logger.info("Submitting %s job (model=%s, prompt=%.80s...)", video_mode, model, prompt)

        def _subscribe():
            return fal_client.subscribe(model, arguments=arguments, with_logs=False)

        try:
            result = await loop.run_in_executor(None, _subscribe)
        except Exception as exc:
            raise FalVideoError(f"Video generation failed ({video_mode}): {exc}") from exc

        # Extract video URL — both models return {"video": {"url": "..."}}
        video_url: str = ""
        if "video" in result and isinstance(result["video"], dict):
            video_url = result["video"].get("url", "")
        elif "video" in result and isinstance(result["video"], str):
            video_url = result["video"]

        if not video_url:
            raise FalVideoError(f"No video URL returned. Keys: {list(result.keys())}")

        logger.info("Video ready — downloading from %s", video_url[:70])
        import urllib.request
        raw_bytes: bytes = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(video_url, timeout=120).read()
        )
        logger.info("Downloaded %d bytes", len(raw_bytes))

        # Only trim for Kling (which generates 5 or 10s natively)
        # MiniMax generates exact duration, no trimming needed
        if video_mode == "premium" and max_duration_seconds < 10:
            raw_bytes = await self._trim(raw_bytes, max_duration_seconds)

        logger.info("Video complete: %d bytes (mode=%s)", len(raw_bytes), video_mode)
        return raw_bytes

    async def _trim(self, video_bytes: bytes, duration_seconds: int) -> bytes:
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
                ["ffmpeg", "-y", "-i", inp_path, "-t", str(duration_seconds), "-c", "copy", out_path],
                capture_output=True,
            )
            if r.returncode != 0:
                logger.warning("ffmpeg trim failed, returning untrimmed: %s", r.stderr[-200:])
                return video_bytes
            return open(out_path, "rb").read()
        finally:
            for p in (inp_path, out_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
