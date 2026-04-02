"""FurniVision AI — Agent 4: Validator — QC consistency check and colour grading."""

import asyncio
import io
import logging
import tempfile
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel

from models.pipeline import FrameStatus
from services.gemini import GeminiService
from services.image_processor import ImageProcessor
from services.storage import StorageService
from config import (
    GCS_PATH_FRAMES_GRADED,
    QC_CONSISTENCY_THRESHOLD,
    TEMP_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """Output of the validation / colour-grading pipeline."""

    room_id: str
    frame_scores: list[dict]  # [{frame_idx, score, issues}]
    overall_score: float
    hero_frame_indices: list[int]
    frames_regenerated: list[int]
    graded_frame_urls: list[str]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ValidatorAgent:
    """Agent 4 — quality-checks rendered frames for visual consistency,
    applies histogram matching and vignette grading, and selects hero frames.
    """

    def __init__(self) -> None:
        self.gemini = GeminiService()
        self.image_processor = ImageProcessor()
        self.storage = StorageService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def validate(
        self,
        frames: list[FrameStatus],
        scene_plan,  # agents.agent2_planner.ScenePlan
        room_id: str,
    ) -> ValidationResult:
        """Run the full validation and grading pipeline.

        Steps
        -----
        1. Download all completed frames from GCS.
        2. Histogram-match all frames to frame 0 (LAB colour space).
        3. Gemini pairwise consistency check on consecutive pairs.
        4. Flag pairs below QC_CONSISTENCY_THRESHOLD for regeneration.
        5. Apply vignette to all frames.
        6. Gemini selects 5 hero frames from the 8 keyframes.
        7. Save graded frames to GCS ``graded/`` path.
        8. Return ValidationResult.
        """
        project_id = scene_plan.project_id

        logger.info(
            "ValidatorAgent.validate — room=%s, project=%s, frames=%d",
            room_id, project_id, len(frames),
        )

        # ------------------------------------------------------------------
        # 1. Download all completed frames from GCS
        # ------------------------------------------------------------------
        completed_frames = [f for f in frames if f.status == "complete" and f.gcs_url]
        completed_frames.sort(key=lambda f: f.frame_idx)

        if not completed_frames:
            logger.error("No completed frames to validate for room %s", room_id)
            return ValidationResult(
                room_id=room_id,
                frame_scores=[],
                overall_score=0.0,
                hero_frame_indices=[],
                frames_regenerated=[],
                graded_frame_urls=[],
            )

        logger.info("Downloading %d completed frames from GCS", len(completed_frames))
        frame_bytes_map: dict[int, bytes] = {}
        download_tasks = []

        for fs in completed_frames:
            download_tasks.append(self._download_frame(fs.frame_idx, fs.gcs_url))

        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

        for fs, result in zip(completed_frames, download_results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to download frame %d: %s", fs.frame_idx, result
                )
            else:
                frame_bytes_map[fs.frame_idx] = result

        if not frame_bytes_map:
            logger.error("Could not download any frames for room %s", room_id)
            return ValidationResult(
                room_id=room_id,
                frame_scores=[],
                overall_score=0.0,
                hero_frame_indices=[],
                frames_regenerated=[],
                graded_frame_urls=[],
            )

        sorted_indices = sorted(frame_bytes_map.keys())
        logger.info("Downloaded %d frames successfully", len(sorted_indices))

        # ------------------------------------------------------------------
        # 2. Histogram matching — normalise all to frame 0's histogram (LAB)
        # ------------------------------------------------------------------
        logger.info("Step 2: Histogram matching to frame 0 reference")

        reference_idx = sorted_indices[0]
        reference_bytes = frame_bytes_map[reference_idx]
        reference_img = self._bytes_to_cv2(reference_bytes)

        matched_images: dict[int, np.ndarray] = {reference_idx: reference_img}

        for idx in sorted_indices[1:]:
            try:
                source_img = self._bytes_to_cv2(frame_bytes_map[idx])
                matched = self.image_processor.match_histograms(source_img, reference_img)
                matched_images[idx] = matched
                logger.debug("Histogram matched frame %d", idx)
            except Exception as exc:
                logger.warning(
                    "Histogram matching failed for frame %d: %s — using original",
                    idx, exc,
                )
                matched_images[idx] = self._bytes_to_cv2(frame_bytes_map[idx])

        # ------------------------------------------------------------------
        # 3. Gemini pairwise consistency check for consecutive pairs
        # ------------------------------------------------------------------
        logger.info("Step 3: Pairwise consistency check (%d pairs)", len(sorted_indices) - 1)

        frame_scores: list[dict] = []
        flagged_frames: list[int] = []

        pair_tasks = []
        pair_indices = []
        for i in range(len(sorted_indices) - 1):
            idx_a = sorted_indices[i]
            idx_b = sorted_indices[i + 1]
            pair_tasks.append(
                self._check_pair_consistency(
                    frame_bytes_map[idx_a], frame_bytes_map[idx_b]
                )
            )
            pair_indices.append((idx_a, idx_b))

        pair_results = await asyncio.gather(*pair_tasks, return_exceptions=True)

        # Build score entries for each frame
        score_by_idx: dict[int, dict] = {}
        for idx in sorted_indices:
            score_by_idx[idx] = {
                "frame_idx": idx,
                "score": 1.0,
                "issues": [],
            }

        for (idx_a, idx_b), result in zip(pair_indices, pair_results):
            if isinstance(result, Exception):
                logger.warning(
                    "Pairwise check failed for frames %d-%d: %s",
                    idx_a, idx_b, result,
                )
                # Assume OK if check fails
                continue

            pair_score = float(result.get("score", 1.0))
            pair_issues = result.get("issues", [])

            logger.info(
                "Pair (%d, %d): score=%.2f, issues=%d",
                idx_a, idx_b, pair_score, len(pair_issues),
            )

            # Update the second frame's score (the one that may diverge)
            if pair_score < score_by_idx[idx_b]["score"]:
                score_by_idx[idx_b]["score"] = pair_score
            score_by_idx[idx_b]["issues"].extend(pair_issues)

            # ------------------------------------------------------------------
            # 4. Flag frames below threshold for regeneration
            # ------------------------------------------------------------------
            if pair_score < QC_CONSISTENCY_THRESHOLD:
                logger.warning(
                    "Frame %d flagged for regeneration (pair score %.2f < %.2f)",
                    idx_b, pair_score, QC_CONSISTENCY_THRESHOLD,
                )
                flagged_frames.append(idx_b)

        frame_scores = [score_by_idx[idx] for idx in sorted_indices]

        # Compute overall score
        all_scores = [entry["score"] for entry in frame_scores]
        overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        logger.info(
            "Pairwise checks complete: overall=%.2f, flagged=%d frames",
            overall_score, len(flagged_frames),
        )

        # ------------------------------------------------------------------
        # 5. Apply vignette to all frames
        # ------------------------------------------------------------------
        logger.info("Step 5: Applying vignette effect to %d frames", len(matched_images))

        graded_images: dict[int, np.ndarray] = {}
        for idx, img in matched_images.items():
            try:
                graded = self.image_processor.apply_vignette(img, strength=0.3)
                graded_images[idx] = graded
            except Exception as exc:
                logger.warning("Vignette failed for frame %d: %s", idx, exc)
                graded_images[idx] = img

        # ------------------------------------------------------------------
        # 6. Gemini selects 5 hero frames from 8 keyframes
        # ------------------------------------------------------------------
        logger.info("Step 6: Selecting hero frames from keyframes")

        keyframe_indices = [
            idx for idx in sorted_indices
            if any(f.frame_idx == idx and f.frame_type == "keyframe" for f in frames)
        ]

        hero_frame_indices: list[int] = []

        if len(keyframe_indices) >= 5:
            # Prepare keyframe images as PNG bytes for Gemini
            keyframe_bytes: list[bytes] = []
            for idx in keyframe_indices:
                png_bytes = self._cv2_to_bytes(graded_images.get(idx, matched_images.get(idx)))
                keyframe_bytes.append(png_bytes)

            try:
                hero_result = await self.gemini.select_hero_frames(keyframe_bytes)
                selected = hero_result.get("selected", [])
                reasoning = hero_result.get("reasoning", "")

                # Map selected indices back to actual frame indices
                hero_frame_indices = [
                    keyframe_indices[i]
                    for i in selected
                    if 0 <= i < len(keyframe_indices)
                ][:5]

                logger.info(
                    "Hero frames selected: %s (reasoning: %s)",
                    hero_frame_indices, reasoning[:200],
                )
            except Exception as exc:
                logger.warning(
                    "Hero selection failed: %s — using first 5 keyframes", exc
                )
                hero_frame_indices = keyframe_indices[:5]
        else:
            # Fewer than 5 keyframes: use all of them
            hero_frame_indices = keyframe_indices[:5]
            logger.info(
                "Only %d keyframes available — using all as heroes",
                len(keyframe_indices),
            )

        # ------------------------------------------------------------------
        # 7. Save graded frames to GCS graded/ path
        # ------------------------------------------------------------------
        logger.info("Step 7: Uploading %d graded frames to GCS", len(graded_images))

        graded_frame_urls: list[str] = []
        upload_tasks = []
        upload_indices = []

        for idx in sorted(graded_images.keys()):
            gcs_path = GCS_PATH_FRAMES_GRADED.format(
                project_id=project_id, room_id=room_id, n=idx
            )
            png_bytes = self._cv2_to_bytes(graded_images[idx])
            upload_tasks.append(
                self.storage.upload_bytes(
                    data=png_bytes,
                    gcs_path=gcs_path,
                    content_type="image/png",
                )
            )
            upload_indices.append((idx, gcs_path))

        upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

        for (idx, gcs_path), result in zip(upload_indices, upload_results):
            if isinstance(result, Exception):
                logger.warning("Failed to upload graded frame %d: %s", idx, result)
            else:
                signed_url = self.storage.get_signed_url(gcs_path)
                graded_frame_urls.append(signed_url)
                logger.debug("Graded frame %d uploaded -> %s", idx, gcs_path)

        # ------------------------------------------------------------------
        # 8. Build and return ValidationResult
        # ------------------------------------------------------------------
        validation_result = ValidationResult(
            room_id=room_id,
            frame_scores=frame_scores,
            overall_score=round(overall_score, 3),
            hero_frame_indices=hero_frame_indices,
            frames_regenerated=flagged_frames,
            graded_frame_urls=graded_frame_urls,
        )

        logger.info(
            "Validation complete — room=%s, overall=%.2f, heroes=%s, flagged=%d, graded=%d",
            room_id,
            overall_score,
            hero_frame_indices,
            len(flagged_frames),
            len(graded_frame_urls),
        )

        return validation_result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _download_frame(self, frame_idx: int, gcs_url: str) -> bytes:
        """Download a single frame from GCS."""
        return await self.storage.download_bytes(gcs_url)

    async def _check_pair_consistency(
        self, frame_a_bytes: bytes, frame_b_bytes: bytes
    ) -> dict:
        """Run Gemini pairwise consistency check on two frame images."""
        return await self.gemini.compare_frame_pair(frame_a_bytes, frame_b_bytes)

    @staticmethod
    def _bytes_to_cv2(png_bytes: bytes) -> np.ndarray:
        """Convert PNG bytes to an OpenCV BGR numpy array."""
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode PNG bytes to OpenCV image")
        return img

    @staticmethod
    def _cv2_to_bytes(img: np.ndarray) -> bytes:
        """Convert an OpenCV BGR image to PNG bytes."""
        success, buf = cv2.imencode(".png", img)
        if not success:
            raise ValueError("Failed to encode OpenCV image to PNG bytes")
        return buf.tobytes()
