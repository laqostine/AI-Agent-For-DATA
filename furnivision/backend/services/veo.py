"""FurniVision AI — Veo 3 video generation with ffmpeg fallback."""

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class VeoError(Exception):
    """Raised when video generation fails."""


class VeoService:
    """Video generation via Veo 3 with automatic ffmpeg fallback."""

    def __init__(self) -> None:
        logger.info("VeoService initialised")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_video_from_frames(
        self,
        frame_paths: list[str],
        motion_descriptors: list[str],
        output_path: str,
        input_fps: int = 4,
        output_fps: int = 24,
    ) -> str:
        """Generate a video from rendered frames.

        Attempts Veo 3 first; on any failure falls back to ffmpeg assembly.
        Returns the path to the final video file.
        """
        if not frame_paths:
            raise VeoError("No frame paths provided")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # --- Attempt Veo 3 ---
        try:
            result = await self._veo3_generate(frame_paths, motion_descriptors, output_path)
            logger.info("Veo 3 succeeded -> %s", result)
            return result
        except Exception as exc:
            logger.warning("Veo 3 generation failed (%s), falling back to ffmpeg", exc)

        # --- ffmpeg fallback ---
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

    # ------------------------------------------------------------------
    # Veo 3 (placeholder — real SDK call when API is available)
    # ------------------------------------------------------------------

    async def _veo3_generate(
        self,
        frame_paths: list[str],
        motion_descriptors: list[str],
        output_path: str,
    ) -> str:
        """Attempt generation via the Veo 3 API.

        Raises ``NotImplementedError`` until the Veo 3 SDK is generally
        available, ensuring the fallback path is exercised.
        """
        # When the Veo 3 SDK ships, integrate here:
        #   from google.cloud.video import generation_v3  # hypothetical
        #   client = generation_v3.VideoGenerationServiceClient()
        #   ...
        raise NotImplementedError("Veo 3 API not yet available — using ffmpeg fallback")

    # ------------------------------------------------------------------
    # ffmpeg fallback
    # ------------------------------------------------------------------

    def _ffmpeg_fallback(
        self,
        frame_paths: list[str],
        output_path: str,
        input_fps: int = 4,
        output_fps: int = 24,
    ) -> str:
        """Assemble frames into an MP4 using ffmpeg with a subtle zoom effect.

        Returns the *output_path* on success.
        """
        if not frame_paths:
            raise VeoError("No frames to assemble")

        # Create a temporary directory for symlinked, zero-padded frame names
        with tempfile.TemporaryDirectory(prefix="furnivision_ffmpeg_") as tmpdir:
            for idx, src in enumerate(sorted(frame_paths)):
                ext = Path(src).suffix or ".png"
                dst = os.path.join(tmpdir, f"frame_{idx:04d}{ext}")
                os.symlink(os.path.abspath(src), dst)

            ext = Path(frame_paths[0]).suffix or ".png"
            input_pattern = os.path.join(tmpdir, f"frame_%04d{ext}")

            # Subtle zoom via scale / zoompan filter
            # zoompan: slow zoom from 100% to 104% across all frames
            total_frames = len(frame_paths) * (output_fps // max(input_fps, 1))
            zoom_increment = 0.04 / max(total_frames, 1)

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(input_fps),
                "-i", input_pattern,
                "-vf", (
                    f"zoompan=z='1+{zoom_increment}*on':x='iw/2-(iw/zoom/2)'"
                    f":y='ih/2-(ih/zoom/2)':d=1:fps={output_fps},"
                    f"scale=trunc(iw/2)*2:trunc(ih/2)*2"
                ),
                "-c:v", "libx264",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ]

            logger.info("Running ffmpeg: %s", " ".join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error("ffmpeg stderr: %s", result.stderr)
                raise VeoError(f"ffmpeg exited with code {result.returncode}: {result.stderr[:500]}")

        logger.info("ffmpeg fallback produced %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # HLS segment generation
    # ------------------------------------------------------------------

    def _generate_hls(self, video_path: str, output_dir: str) -> str:
        """Generate HLS segments and playlist from *video_path*.

        Returns the path to the master ``.m3u8`` playlist file.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        playlist_path = os.path.join(output_dir, "room.m3u8")
        segment_pattern = os.path.join(output_dir, "segment_%03d.ts")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-c:v", "libx264",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-hls_segment_filename", segment_pattern,
            "-f", "hls",
            playlist_path,
        ]

        logger.info("Generating HLS: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error("ffmpeg HLS stderr: %s", result.stderr)
            raise VeoError(f"HLS generation failed (code {result.returncode}): {result.stderr[:500]}")

        logger.info("HLS playlist -> %s", playlist_path)
        return playlist_path
