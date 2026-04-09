"""FurniVision AI — Agent 5: Animator — video generation + viewer manifest.

Video generation priority:
  1. fal.ai Kling v2.1 image-to-video  (primary — high rate limits)
  2. Veo 3 Fast                         (fallback if fal.ai unavailable)
  3. ffmpeg slideshow                   (last resort)
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from models.pipeline import FrameStatus
from services.storage import StorageService
from services.veo import VeoService, VeoError
from config import (
    FAL_KEY,
    GCS_PATH_VIDEO,
    GCS_PATH_VIEWER_MANIFEST,
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
    preview_url: str | None = None
    master_video_url: str | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AnimatorAgent:
    """Agent 5 — generates room walkthrough video via Veo 3."""

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
        reference_images: list[bytes] | None = None,
    ) -> AnimationResult:
        """Generate a Veo 3 room-walkthrough video using keyframe + prompt.

        Steps
        -----
        1. Download the wide-shot keyframe (frame 0) from storage.
        2. Build a cinematic prompt from the scene plan.
        3. Call Veo 3 to generate an 8-second video.
        4. Upload video to storage.
        5. Build viewer_manifest.json.
        6. Return AnimationResult.
        """
        logger.info(
            "AnimatorAgent.animate — project=%s, room=%s, frames=%d",
            project_id, room_id, len(validated_frames),
        )

        completed = [f for f in validated_frames if f.status == "complete"]
        completed.sort(key=lambda f: f.frame_idx)

        # ------------------------------------------------------------------
        # 1. Resolve start frame (keyframe 0) and end frame (keyframe 1)
        #    Start frame priority: uploaded reference render > keyframe 0
        #    End frame: always keyframe 1 (the second generated shot)
        # ------------------------------------------------------------------
        reference_image: bytes | None = None   # start frame for Veo fallback
        start_frame:     bytes | None = None   # start frame for Kling
        end_frame:       bytes | None = None   # end frame for Kling (keyframe 1)

        # Download generated keyframes so we can use them as start/end
        if len(completed) >= 2:
            try:
                start_frame = await self.storage.download_bytes(completed[0].gcs_url)
                end_frame   = await self.storage.download_bytes(completed[1].gcs_url)
                logger.info(
                    "Loaded keyframe start=%d bytes, end=%d bytes",
                    len(start_frame), len(end_frame),
                )
            except Exception as exc:
                logger.warning("Could not download keyframes: %s", exc)
        elif len(completed) == 1:
            try:
                start_frame = await self.storage.download_bytes(completed[0].gcs_url)
            except Exception as exc:
                logger.warning("Could not download keyframe 0: %s", exc)

        # If a reference render was uploaded, use it as the start frame
        # (it's a higher-fidelity view of the actual room)
        if reference_images:
            start_frame     = reference_images[0]
            reference_image = reference_images[0]
            logger.info(
                "Using uploaded reference render as start frame (%d bytes)",
                len(start_frame),
            )
        elif start_frame:
            reference_image = start_frame

        # ------------------------------------------------------------------
        # 2. Build cinematic Veo prompt (include furniture if available)
        # ------------------------------------------------------------------
        room_label = getattr(scene_plan.room, "label", "room")
        style = getattr(scene_plan, "style_anchor", "modern interior")

        # Include furniture layout in the prompt
        furniture_desc = ""
        layout = getattr(scene_plan, "furniture_layout", [])
        if layout:
            items = [item.get("item_name", item.get("item_id", "")) for item in layout[:6]]
            items = [i for i in items if i]
            if items:
                furniture_desc = f"Furnished with: {', '.join(items)}. "

        if reference_images:
            veo_prompt = (
                f"Slow gentle dolly shot inside a {room_label}. "
                f"{furniture_desc}"
                f"Camera glides forward very slowly, barely moving, revealing the room depth. "
                f"Exactly the same room, same furniture, same materials, same lighting throughout. "
                f"V-Ray architectural visualization quality, photorealistic 4K, no people."
            )
        else:
            veo_prompt = (
                f"Slow gentle dolly shot inside a {room_label}. "
                f"{furniture_desc}"
                f"Style: {style[:120]}. "
                f"Camera glides forward slowly revealing the space. "
                f"Photorealistic 4K architectural visualization, no people."
            )

        # ------------------------------------------------------------------
        # 3. Generate video — fal.ai Kling (primary) → Veo 3 → ffmpeg
        # ------------------------------------------------------------------
        work_dir = os.path.join(str(TEMP_DIR), project_id, room_id, "video")
        os.makedirs(work_dir, exist_ok=True)
        video_local_path = os.path.join(work_dir, "room_video.mp4")

        video_bytes: bytes | None = None

        # --- 3a. fal.ai Kling (primary) — start frame + end frame arc ---
        if FAL_KEY and start_frame:
            try:
                from services.fal_video import FalVideoService
                fal = FalVideoService()
                video_bytes = await fal.generate_video(
                    start_frame_bytes=start_frame,
                    prompt=veo_prompt,
                    end_frame_bytes=end_frame,   # keyframe 1 → camera arc
                    max_duration_seconds=7,
                    aspect_ratio="16:9",
                )
                Path(video_local_path).write_bytes(video_bytes)
                logger.info(
                    "Kling video generated: %d bytes (start+end frame mode=%s)",
                    len(video_bytes), end_frame is not None,
                )
            except Exception as exc:
                logger.warning("Kling (fal.ai) failed: %s — trying Veo 3", exc)
                video_bytes = None

        # --- 3b. Veo 3 (fallback) ---
        if not video_bytes:
            try:
                video_bytes = await self.veo.generate_video_from_prompt(
                    prompt=veo_prompt,
                    reference_image_bytes=reference_image,
                    output_path=video_local_path,
                    duration_seconds=8,
                    aspect_ratio="16:9",
                )
                logger.info("Veo 3 video generated: %d bytes", len(video_bytes))
            except Exception as exc:
                logger.warning("Veo 3 failed: %s — falling back to ffmpeg", exc)
                video_bytes = None

        # --- 3c. ffmpeg slideshow (last resort) ---
        if not video_bytes:
            frame_paths = []
            for fs in completed:
                if not fs.gcs_url:
                    continue
                local_p = os.path.join(work_dir, f"frame_{fs.frame_idx:03d}.png")
                try:
                    await self.storage.download_file(fs.gcs_url, local_p)
                    frame_paths.append(local_p)
                except Exception as dl_exc:
                    logger.warning("Could not download frame %d: %s", fs.frame_idx, dl_exc)
            if not frame_paths and reference_image:
                tmp_img = os.path.join(work_dir, "ref_frame.png")
                Path(tmp_img).write_bytes(reference_image)
                frame_paths = [tmp_img] * 4
            if frame_paths:
                logger.info("ffmpeg fallback with %d frames", len(frame_paths))
                await self.veo.generate_video_from_frames(
                    frame_paths=frame_paths,
                    motion_descriptors=[],
                    output_path=video_local_path,
                )
                video_bytes = Path(video_local_path).read_bytes()
            else:
                raise VeoError("No frames or reference image available for video generation")

        # ------------------------------------------------------------------
        # 4. Upload video to storage
        # ------------------------------------------------------------------
        video_gcs_path = GCS_PATH_VIDEO.format(project_id=project_id, room_id=room_id)
        await self.storage.upload_bytes(
            data=video_bytes,
            gcs_path=video_gcs_path,
            content_type="video/mp4",
        )
        video_url = self.storage.get_signed_url(video_gcs_path)
        logger.info("Video uploaded -> %s", video_url[:100])

        # ------------------------------------------------------------------
        # 5. Build viewer manifest
        # ------------------------------------------------------------------
        manifest = {
            "room_id": room_id,
            "project_id": project_id,
            "video_url": video_url,
            "keyframes": [
                {
                    "frame_idx": fs.frame_idx,
                    "url": self.storage.get_signed_url(fs.gcs_url) if fs.gcs_url else None,
                    "frame_type": fs.frame_type,
                }
                for fs in completed
            ],
            "camera_positions": [
                cp.model_dump() for cp in scene_plan.camera_positions[:2]
            ],
            "style_anchor": style[:300],
        }

        manifest_gcs_path = GCS_PATH_VIEWER_MANIFEST.format(
            project_id=project_id, room_id=room_id
        )
        await self.storage.upload_bytes(
            data=json.dumps(manifest, indent=2).encode(),
            gcs_path=manifest_gcs_path,
            content_type="application/json",
        )
        manifest_url = self.storage.get_signed_url(manifest_gcs_path)

        logger.info("AnimatorAgent complete for room %s — video=%s", room_id, video_url[:80])

        return AnimationResult(
            room_id=room_id,
            video_url=video_url,
            hls_url=None,
            viewer_manifest_url=manifest_url,
            preview_url=self.storage.get_signed_url(completed[0].gcs_url) if completed else None,
        )
