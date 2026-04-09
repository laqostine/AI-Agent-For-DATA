"""FurniVision AI — Veo 3 video generation service."""

import asyncio
import logging
from pathlib import Path

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

_VEO_MODEL = "veo-3.0-fast-generate-001"
_POLL_INTERVAL = 5   # seconds between status checks
_MAX_WAIT = 600      # 10 minutes max


class VeoError(Exception):
    """Raised when video generation fails."""


class VeoService:
    """Video generation via Veo 3 with ffmpeg fallback."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("VeoService initialised (model=%s)", _VEO_MODEL)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_video_from_prompt(
        self,
        prompt: str,
        reference_image_bytes: bytes | None = None,
        output_path: str | None = None,
        duration_seconds: int = 8,
        aspect_ratio: str = "16:9",
    ) -> bytes:
        """Generate a video via Veo 3.

        Parameters
        ----------
        prompt:
            Text description of the scene / camera motion.
        reference_image_bytes:
            Optional PNG/JPEG bytes to use as a style/composition reference.
        output_path:
            If provided, write the MP4 bytes to this path as well.
        duration_seconds:
            Length of output video (4–8).
        aspect_ratio:
            Aspect ratio string, e.g. '16:9'.

        Returns
        -------
        bytes
            Raw MP4 video bytes.
        """
        loop = asyncio.get_running_loop()

        logger.info(
            "Veo 3 generation starting — prompt=%.100s..., duration=%ds, ref_image=%s",
            prompt, duration_seconds, reference_image_bytes is not None,
        )

        # Build image input if provided
        image_input = None
        if reference_image_bytes:
            image_input = types.Image(image_bytes=reference_image_bytes, mime_type="image/png")

        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            duration_seconds=max(4, min(8, duration_seconds)),
            number_of_videos=1,
        )

        # Start the async operation
        try:
            if image_input:
                operation = await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_videos(
                        model=_VEO_MODEL,
                        prompt=prompt,
                        image=image_input,
                        config=config,
                    ),
                )
            else:
                operation = await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_videos(
                        model=_VEO_MODEL,
                        prompt=prompt,
                        config=config,
                    ),
                )
        except Exception as exc:
            raise VeoError(f"Failed to start Veo generation: {exc}") from exc

        logger.info("Veo operation started: %s", getattr(operation, "name", "unknown"))

        # Poll until done
        elapsed = 0
        while elapsed < _MAX_WAIT:
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            try:
                operation = await loop.run_in_executor(
                    None,
                    lambda op=operation: self._client.operations.get(op),
                )
            except Exception as exc:
                logger.warning("Poll error (elapsed=%ds): %s", elapsed, exc)
                continue

            done = getattr(operation, "done", False)
            logger.info("Veo poll — elapsed=%ds, done=%s", elapsed, done)

            if done:
                break
        else:
            raise VeoError(f"Veo generation timed out after {_MAX_WAIT}s")

        # Extract video bytes (may be inline bytes or a URI to download)
        try:
            videos = operation.response.generated_videos
            if not videos:
                raise VeoError("Veo returned no videos")
            video = videos[0].video

            video_bytes: bytes | None = getattr(video, "video_bytes", None)

            if not video_bytes:
                # URI-based response — download the video
                uri = getattr(video, "uri", None)
                if not uri:
                    raise VeoError("Veo video has neither bytes nor URI")
                logger.info("Downloading Veo video from URI: %s", uri[:80])
                import urllib.request as _url_req
                req = _url_req.Request(uri, headers={"x-goog-api-key": GOOGLE_API_KEY})
                resp = await loop.run_in_executor(
                    None,
                    lambda: _url_req.urlopen(req, timeout=60),
                )
                video_bytes = resp.read()

            if not video_bytes:
                raise VeoError("Veo video download returned empty bytes")
        except VeoError:
            raise
        except Exception as exc:
            raise VeoError(f"Failed to extract video from Veo response: {exc}") from exc

        logger.info("Veo 3 complete — %d bytes", len(video_bytes))

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(video_bytes)
            logger.info("Video written to %s", output_path)

        return video_bytes

    # ------------------------------------------------------------------
    # Legacy compatibility: generate_video_from_frames (ffmpeg fallback)
    # Used if caller passes pre-rendered frames instead of prompts.
    # ------------------------------------------------------------------

    async def generate_video_from_frames(
        self,
        frame_paths: list[str],
        motion_descriptors: list[str],
        output_path: str,
        input_fps: int = 4,
        output_fps: int = 24,
    ) -> str:
        """Assemble frames into MP4 via ffmpeg (legacy path)."""
        if not frame_paths:
            raise VeoError("No frame paths provided")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._ffmpeg_fallback,
            frame_paths,
            output_path,
            input_fps,
            output_fps,
        )
        return result

    def _ffmpeg_fallback(
        self,
        frame_paths: list[str],
        output_path: str,
        input_fps: int = 4,
        output_fps: int = 24,
    ) -> str:
        import subprocess, tempfile, os
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        concat_file = os.path.join(tempfile.mkdtemp(), "concat.txt")
        with open(concat_file, "w") as f:
            for fp in sorted(frame_paths):
                f.write(f"file '{fp}'\n")
                f.write(f"duration {1 / input_fps}\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", f"fps={output_fps},scale=1280:720",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise VeoError(f"ffmpeg failed: {result.stderr[:500]}")
        logger.info("ffmpeg assembled video -> %s", output_path)
        return output_path

    def _generate_hls(self, video_path: str, hls_dir: str) -> str:
        """Generate HLS playlist from video."""
        import subprocess, os
        os.makedirs(hls_dir, exist_ok=True)
        playlist = os.path.join(hls_dir, "playlist.m3u8")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-codec:", "copy",
            "-start_number", "0",
            "-hls_time", "2",
            "-hls_list_size", "0",
            "-f", "hls",
            playlist,
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        return playlist
