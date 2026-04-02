"""FurniVision AI — Agent 5: Animator — Video assembly and viewer manifest."""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from models.pipeline import FrameStatus
from services.storage import StorageService
from services.veo import VeoService, VeoError
from config import (
    GCS_PATH_FRAMES_GRADED,
    GCS_PATH_VIDEO,
    GCS_PATH_HLS,
    GCS_PATH_VIEWER_MANIFEST,
    GCS_PATH_MASTER_VIDEO,
    TEMP_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class AnimationResult(BaseModel):
    """Output of the animation / video assembly pipeline."""

    room_id: str
    video_url: str
    hls_url: str | None = None
    viewer_manifest_url: str
    master_video_url: str | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AnimatorAgent:
    """Agent 5 — assembles graded frames into video, HLS, and viewer data."""

    def __init__(self) -> None:
        self.veo = VeoService()
        self.storage = StorageService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def animate(
        self,
        validated_frames: list[FrameStatus],
        scene_plan,  # agents.agent2_planner.ScenePlan
        project_id: str,
        room_id: str,
        all_rooms_complete: bool = False,
    ) -> AnimationResult:
        """Assemble validated frames into a video and build viewer data.

        Steps
        -----
        1. Download graded frames from GCS ordered 000-031.
        2. Attempt Veo 3 API; fallback to ffmpeg (4fps in -> 24fps out).
        3. Upload video to GCS.
        4. Generate HLS segments.
        5. Build viewer_manifest.json with frame URLs, camera positions, types.
        6. Save manifest to GCS.
        7. If all_rooms_complete: build master multi-room video.
        8. Return AnimationResult.
        """
        logger.info(
            "AnimatorAgent.animate — project=%s, room=%s, frames=%d, all_rooms=%s",
            project_id, room_id, len(validated_frames), all_rooms_complete,
        )

        # ------------------------------------------------------------------
        # 1. Download graded frames from GCS ordered 000-031
        # ------------------------------------------------------------------
        completed = [
            f for f in validated_frames
            if f.status == "complete"
        ]
        completed.sort(key=lambda f: f.frame_idx)

        if not completed:
            logger.error("No completed frames to animate for room %s", room_id)
            raise VeoError(f"No completed frames available for room {room_id}")

        # Create a temp directory for this room's frames
        work_dir = os.path.join(str(TEMP_DIR), project_id, room_id, "animation")
        os.makedirs(work_dir, exist_ok=True)

        logger.info("Downloading %d graded frames to %s", len(completed), work_dir)
        local_frame_paths: list[str] = []
        download_tasks = []

        for fs in completed:
            graded_gcs_path = GCS_PATH_FRAMES_GRADED.format(
                project_id=project_id, room_id=room_id, n=fs.frame_idx
            )
            local_path = os.path.join(work_dir, f"frame_{fs.frame_idx:03d}.png")
            download_tasks.append(
                self._download_frame_to_file(graded_gcs_path, local_path, fs.frame_idx)
            )

        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

        for fs, result in zip(completed, download_results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to download graded frame %d: %s — trying raw frame",
                    fs.frame_idx, result,
                )
                # Fallback: try to download the raw frame if graded is missing
                if fs.gcs_url:
                    local_path = os.path.join(work_dir, f"frame_{fs.frame_idx:03d}.png")
                    try:
                        await self.storage.download_file(fs.gcs_url, local_path)
                        local_frame_paths.append(local_path)
                    except Exception as exc2:
                        logger.error(
                            "Could not download raw frame %d either: %s",
                            fs.frame_idx, exc2,
                        )
            else:
                local_frame_paths.append(result)

        local_frame_paths.sort()

        if not local_frame_paths:
            raise VeoError(f"Could not download any frames for room {room_id}")

        logger.info("Downloaded %d frames locally", len(local_frame_paths))

        # ------------------------------------------------------------------
        # 2. Attempt Veo 3 API, fallback to ffmpeg (4fps -> 24fps)
        # ------------------------------------------------------------------
        video_local_path = os.path.join(work_dir, "room.mp4")

        # Build motion descriptors from scene plan for Veo
        motion_descriptors = self._build_motion_descriptors(scene_plan, completed)

        logger.info("Generating video from %d frames", len(local_frame_paths))
        video_path = await self.veo.generate_video_from_frames(
            frame_paths=local_frame_paths,
            motion_descriptors=motion_descriptors,
            output_path=video_local_path,
            input_fps=4,
            output_fps=24,
        )
        logger.info("Video generated at %s", video_path)

        # ------------------------------------------------------------------
        # 3. Upload video to GCS
        # ------------------------------------------------------------------
        video_gcs_path = GCS_PATH_VIDEO.format(
            project_id=project_id, room_id=room_id
        )
        await self.storage.upload_file(video_path, video_gcs_path)
        video_url = self.storage.get_signed_url(video_gcs_path)
        logger.info("Video uploaded -> %s", video_gcs_path)

        # ------------------------------------------------------------------
        # 4. Generate HLS segments
        # ------------------------------------------------------------------
        hls_url: str | None = None
        hls_dir = os.path.join(work_dir, "hls")

        try:
            hls_playlist_path = self.veo._generate_hls(video_path, hls_dir)
            logger.info("HLS generated at %s", hls_playlist_path)

            # Upload all HLS files to GCS
            hls_gcs_prefix = GCS_PATH_HLS.format(
                project_id=project_id, room_id=room_id
            ).rsplit("/", 1)[0]  # Get the directory portion

            hls_files = list(Path(hls_dir).glob("*"))
            for hls_file in hls_files:
                hls_gcs_path = f"{hls_gcs_prefix}/{hls_file.name}"
                await self.storage.upload_file(str(hls_file), hls_gcs_path)

            # The main playlist URL
            hls_playlist_gcs = GCS_PATH_HLS.format(
                project_id=project_id, room_id=room_id
            )
            hls_url = self.storage.get_signed_url(hls_playlist_gcs)
            logger.info("HLS uploaded, playlist -> %s", hls_playlist_gcs)

        except Exception as exc:
            logger.warning("HLS generation failed: %s — skipping", exc)
            hls_url = None

        # ------------------------------------------------------------------
        # 5. Build viewer_manifest.json
        # ------------------------------------------------------------------
        viewer_manifest = self._build_viewer_manifest(
            scene_plan=scene_plan,
            completed_frames=completed,
            project_id=project_id,
            room_id=room_id,
            video_url=video_url,
        )

        manifest_local_path = os.path.join(work_dir, "viewer_manifest.json")
        with open(manifest_local_path, "w") as f:
            json.dump(viewer_manifest, f, indent=2)

        logger.info("Viewer manifest built with %d frames", len(viewer_manifest.get("frames", [])))

        # ------------------------------------------------------------------
        # 6. Save manifest to GCS
        # ------------------------------------------------------------------
        manifest_gcs_path = GCS_PATH_VIEWER_MANIFEST.format(
            project_id=project_id, room_id=room_id
        )
        manifest_bytes = json.dumps(viewer_manifest, indent=2).encode("utf-8")
        await self.storage.upload_bytes(
            data=manifest_bytes,
            gcs_path=manifest_gcs_path,
            content_type="application/json",
        )
        viewer_manifest_url = self.storage.get_signed_url(manifest_gcs_path)
        logger.info("Viewer manifest uploaded -> %s", manifest_gcs_path)

        # ------------------------------------------------------------------
        # 7. If all_rooms_complete: build master multi-room video
        # ------------------------------------------------------------------
        master_video_url: str | None = None

        if all_rooms_complete:
            try:
                master_video_url = await self._build_master_video(
                    project_id=project_id,
                    current_room_video_path=video_path,
                )
                logger.info("Master video assembled -> %s", master_video_url)
            except Exception as exc:
                logger.warning("Master video assembly failed: %s", exc)
                master_video_url = None

        # ------------------------------------------------------------------
        # 8. Return AnimationResult
        # ------------------------------------------------------------------
        result = AnimationResult(
            room_id=room_id,
            video_url=video_url,
            hls_url=hls_url,
            viewer_manifest_url=viewer_manifest_url,
            master_video_url=master_video_url,
        )

        logger.info(
            "Animation complete — room=%s, video=%s, hls=%s, manifest=%s",
            room_id,
            video_url[:80] if video_url else "none",
            "yes" if hls_url else "no",
            viewer_manifest_url[:80] if viewer_manifest_url else "none",
        )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _download_frame_to_file(
        self, gcs_path: str, local_path: str, frame_idx: int
    ) -> str:
        """Download a single frame from GCS to a local file path."""
        await self.storage.download_file(gcs_path, local_path)
        return local_path

    def _build_motion_descriptors(
        self,
        scene_plan,
        completed_frames: list[FrameStatus],
    ) -> list[str]:
        """Build motion descriptor strings for Veo from the scene plan.

        Each descriptor explains the camera movement between consecutive frames.
        """
        descriptors: list[str] = []
        num_cameras = len(scene_plan.camera_positions)

        for i, fs in enumerate(completed_frames):
            frame_idx = fs.frame_idx
            camera_idx = frame_idx // 4 if num_cameras > 0 else 0
            local_idx = frame_idx % 4

            if camera_idx < num_cameras:
                camera = scene_plan.camera_positions[camera_idx]
                desc = camera.look_at_description
            else:
                desc = "room interior"

            if local_idx == 0:
                descriptors.append(f"Cut to new angle: {desc}")
            else:
                fraction = local_idx / 4
                descriptors.append(
                    f"Smooth dolly transition ({fraction:.0%} progress) "
                    f"toward {desc}"
                )

        return descriptors

    def _build_viewer_manifest(
        self,
        scene_plan,
        completed_frames: list[FrameStatus],
        project_id: str,
        room_id: str,
        video_url: str,
    ) -> dict:
        """Build the viewer_manifest.json structure.

        Contains all frame URLs, camera positions, frame types, and video URL
        for the interactive 3D viewer.
        """
        frames_data: list[dict] = []
        num_cameras = len(scene_plan.camera_positions)

        for fs in completed_frames:
            frame_idx = fs.frame_idx
            camera_idx = frame_idx // 4 if num_cameras > 0 else 0

            # Build GCS path for graded frame
            graded_gcs_path = GCS_PATH_FRAMES_GRADED.format(
                project_id=project_id, room_id=room_id, n=frame_idx
            )

            # Get camera position data
            camera_data = {}
            if camera_idx < num_cameras:
                cam = scene_plan.camera_positions[camera_idx]
                camera_data = {
                    "pos_x": cam.pos_x,
                    "pos_y": cam.pos_y,
                    "height_m": cam.height_m,
                    "look_at_x": cam.look_at_x,
                    "look_at_y": cam.look_at_y,
                    "fov_deg": cam.fov_deg,
                    "look_at_description": cam.look_at_description,
                }

            frame_entry = {
                "frame_idx": frame_idx,
                "frame_type": fs.frame_type,
                "gcs_path": graded_gcs_path,
                "frame_url": self.storage.get_signed_url(graded_gcs_path),
                "camera": camera_data,
            }
            frames_data.append(frame_entry)

        manifest = {
            "project_id": project_id,
            "room_id": room_id,
            "room_label": scene_plan.room.label,
            "style_anchor": scene_plan.style_anchor,
            "total_frames": len(frames_data),
            "total_cameras": num_cameras,
            "video_url": video_url,
            "frames": frames_data,
            "furniture_layout": scene_plan.furniture_layout,
            "camera_positions": [
                {
                    "index": i,
                    "pos_x": cam.pos_x,
                    "pos_y": cam.pos_y,
                    "height_m": cam.height_m,
                    "look_at_x": cam.look_at_x,
                    "look_at_y": cam.look_at_y,
                    "fov_deg": cam.fov_deg,
                    "look_at_description": cam.look_at_description,
                }
                for i, cam in enumerate(scene_plan.camera_positions)
            ],
        }

        return manifest

    async def _build_master_video(
        self,
        project_id: str,
        current_room_video_path: str,
    ) -> str | None:
        """Build a master multi-room video by concatenating all room videos.

        Discovers all room videos under the project in GCS, downloads them,
        and concatenates with ffmpeg.
        """
        import subprocess

        logger.info("Building master multi-room video for project %s", project_id)

        # List all room video files in the project
        video_prefix = f"projects/{project_id}/rooms/"
        all_files = await self.storage.list_files(video_prefix)
        video_files = [f for f in all_files if f.endswith("/video/room.mp4")]
        video_files.sort()

        if len(video_files) < 2:
            logger.info(
                "Only %d room video(s) found — skipping master video",
                len(video_files),
            )
            return None

        # Download all room videos to temp dir
        master_dir = os.path.join(str(TEMP_DIR), project_id, "master")
        os.makedirs(master_dir, exist_ok=True)

        local_videos: list[str] = []
        for i, gcs_path in enumerate(video_files):
            local_path = os.path.join(master_dir, f"room_{i:02d}.mp4")
            try:
                await self.storage.download_file(gcs_path, local_path)
                local_videos.append(local_path)
            except Exception as exc:
                logger.warning("Failed to download room video %s: %s", gcs_path, exc)

        if len(local_videos) < 2:
            logger.info("Not enough room videos downloaded for master assembly")
            return None

        # Build ffmpeg concat file
        concat_file = os.path.join(master_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for vp in local_videos:
                f.write(f"file '{vp}'\n")

        master_output = os.path.join(master_dir, "walkthrough.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            master_output,
        ]

        logger.info("Running ffmpeg concat: %s", " ".join(cmd))

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=600),
        )

        if result.returncode != 0:
            logger.error("Master video ffmpeg failed: %s", result.stderr[:500])
            raise VeoError(f"Master video concat failed: {result.stderr[:300]}")

        # Upload master video to GCS
        master_gcs_path = GCS_PATH_MASTER_VIDEO.format(project_id=project_id)
        await self.storage.upload_file(master_output, master_gcs_path)
        master_url = self.storage.get_signed_url(master_gcs_path)

        logger.info("Master video uploaded -> %s", master_gcs_path)
        return master_url
