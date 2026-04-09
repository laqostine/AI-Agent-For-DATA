"""FurniVision AI — Video Compiler service.

Concatenates per-room walkthrough videos into a final deliverable:
  - Room videos in order (7s each)
  - Optional ambient background music
  - Logo end card (3s)
  - Output scaled to 1920x1080
  - Uses ffmpeg subprocess calls
"""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from config import TEMP_DIR

logger = logging.getLogger(__name__)

# Duration of the logo end card in seconds
LOGO_END_CARD_DURATION = 3
# Background color for logo card
LOGO_BG_COLOR = "black"


class VideoCompilerError(Exception):
    """Raised when video compilation fails."""


class VideoCompiler:
    """Compile room videos + music + logo into a final MP4."""

    async def compile(
        self,
        room_video_paths: list[str],
        output_path: str,
        logo_path: str | None = None,
        music_path: str | None = None,
        target_width: int = 1920,
        target_height: int = 1080,
    ) -> str:
        """Compile all room videos into a single final MP4.

        Parameters
        ----------
        room_video_paths : list[str]
            Ordered list of room video file paths.
        output_path : str
            Where to save the final MP4.
        logo_path : str | None
            Path to logo image for end card. If None, no end card.
        music_path : str | None
            Path to ambient music file. If None, no background music.
        target_width, target_height : int
            Output resolution (default 1920x1080).

        Returns
        -------
        str
            Path to the final compiled video.
        """
        if not room_video_paths:
            raise VideoCompilerError("No room videos provided")

        # Verify ffmpeg is available
        if not shutil.which("ffmpeg"):
            raise VideoCompilerError("ffmpeg not found in PATH")

        work_dir = Path(tempfile.mkdtemp(prefix="furnivision_compile_"))

        try:
            # Step 1: Scale all room videos to target resolution
            scaled_videos = await self._scale_videos(
                room_video_paths, work_dir, target_width, target_height
            )

            # Step 2: Generate logo end card video if logo provided
            if logo_path and Path(logo_path).exists():
                logo_video = await self._create_logo_end_card(
                    logo_path, work_dir, target_width, target_height
                )
                scaled_videos.append(logo_video)

            # Step 3: Concatenate all videos
            concat_path = await self._concat_videos(scaled_videos, work_dir)

            # Step 4: Add background music if provided
            if music_path and Path(music_path).exists():
                final_path = await self._add_music(concat_path, music_path, work_dir)
            else:
                final_path = concat_path

            # Step 5: Move to output path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_path, output_path)

            logger.info("Video compilation complete: %s", output_path)
            return output_path

        finally:
            # Cleanup work directory
            shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    async def _scale_videos(
        self,
        video_paths: list[str],
        work_dir: Path,
        width: int,
        height: int,
    ) -> list[str]:
        """Scale all videos to the target resolution."""
        width = self._ensure_even(width)
        height = self._ensure_even(height)
        scaled = []
        for i, vpath in enumerate(video_paths):
            if not Path(vpath).exists():
                logger.warning("Room video not found, skipping: %s", vpath)
                continue

            output = str(work_dir / f"scaled_{i:03d}.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", vpath,
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                       f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output,
            ]
            await self._run_ffmpeg(cmd)
            scaled.append(output)

        if not scaled:
            raise VideoCompilerError("No valid room videos to compile")
        return scaled

    async def _create_logo_end_card(
        self,
        logo_path: str,
        work_dir: Path,
        width: int,
        height: int,
    ) -> str:
        """Create a video end card from a logo image."""
        width = self._ensure_even(width)
        height = self._ensure_even(height)
        output = str(work_dir / "logo_card.mp4")
        # Scale logo to fit within 40% of frame height, center on black background
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", logo_path,
            "-t", str(LOGO_END_CARD_DURATION),
            "-vf",
            f"scale=-1:'min(ih,{height}*0.4)',"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={LOGO_BG_COLOR}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            output,
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _concat_videos(
        self, video_paths: list[str], work_dir: Path
    ) -> str:
        """Concatenate videos using ffmpeg concat demuxer."""
        # Write concat list file
        list_path = work_dir / "concat_list.txt"
        with open(list_path, "w") as f:
            for vpath in video_paths:
                f.write(f"file '{vpath}'\n")

        output = str(work_dir / "concatenated.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output,
        ]
        await self._run_ffmpeg(cmd)
        return output

    async def _add_music(
        self, video_path: str, music_path: str, work_dir: Path
    ) -> str:
        """Mix background music with the video audio track."""
        output = str(work_dir / "final_with_music.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            "[1:a]volume=0.3[music];"  # Background music at 30% volume
            "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output,
        ]
        try:
            await self._run_ffmpeg(cmd)
            return output
        except VideoCompilerError:
            # If mixing fails (e.g. no audio in original), try simple overlay
            logger.warning("Audio mix failed, trying simple music overlay")
            cmd2 = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", music_path,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                output,
            ]
            await self._run_ffmpeg(cmd2)
            return output

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_even(n: int) -> int:
        """H.264 requires width/height divisible by 2."""
        return (n // 2) * 2

    # ------------------------------------------------------------------
    # ffmpeg runner
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_ffmpeg(cmd: list[str], timeout: int = 300) -> None:
        """Run an ffmpeg command asynchronously."""
        logger.debug("ffmpeg: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise VideoCompilerError(f"ffmpeg timed out after {timeout}s")

        if proc.returncode != 0:
            err_text = stderr.decode(errors="replace")[-500:]
            raise VideoCompilerError(f"ffmpeg failed (rc={proc.returncode}): {err_text}")
