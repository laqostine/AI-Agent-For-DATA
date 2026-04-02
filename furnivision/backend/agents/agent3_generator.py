"""FurniVision AI — Agent 3: Generator — Imagen 3 frame generation."""

import asyncio
import logging
from datetime import datetime

from models.pipeline import FrameStatus
from services.imagen import ImagenService, ImagenError
from services.storage import StorageService
from config import (
    GCS_PATH_FRAMES_RAW,
    MAX_CONCURRENT_IMAGEN_CALLS,
    MAX_REGENERATION_ATTEMPTS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt softening helper
# ---------------------------------------------------------------------------

_SOFTEN_REMOVALS = [
    "8K ultra detailed",
    "shot on Canon EOS R5, 35mm lens, f/4.0, ISO 200",
    "CRITICAL: ",
]

_SOFTEN_REPLACEMENTS = {
    "photorealistic architectural interior render": "high quality interior render",
    "warm neutral colour grade": "neutral colour grade",
}


def _soften_prompt(prompt: str) -> str:
    """Produce a less aggressive prompt for retry after repeated failures.

    Removes overly specific technical terms that some models may reject and
    simplifies stylistic directives.
    """
    softened = prompt
    for removal in _SOFTEN_REMOVALS:
        softened = softened.replace(removal, "")
    for old, new in _SOFTEN_REPLACEMENTS.items():
        softened = softened.replace(old, new)
    # Clean up double spaces and trailing commas
    while "  " in softened:
        softened = softened.replace("  ", " ")
    softened = softened.replace(", ,", ",").replace(",,", ",").strip()
    return softened


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class GeneratorAgent:
    """Agent 3 — generates all 32 frames for a room via Imagen 3."""

    def __init__(self) -> None:
        self.imagen = ImagenService()
        self.storage = StorageService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_all_frames(
        self,
        scene_plan,  # agents.agent2_planner.ScenePlan
        project_id: str,
        room_id: str,
        job_id: str,
    ) -> list[FrameStatus]:
        """Fire all 32 Imagen 3 calls concurrently (Semaphore-limited).

        Parameters
        ----------
        scene_plan:
            The ScenePlan produced by Agent 2 (contains prompts, frame_types).
        project_id:
            Project identifier for GCS path construction.
        room_id:
            Room identifier for GCS path construction.
        job_id:
            Pipeline job identifier for event/logging context.

        Returns
        -------
        list[FrameStatus]
            One status entry per frame (32 total).
        """
        num_frames = len(scene_plan.prompts)
        logger.info(
            "GeneratorAgent.generate_all_frames — project=%s, room=%s, job=%s, frames=%d",
            project_id, room_id, job_id, num_frames,
        )

        # Initialise frame statuses
        frame_statuses: list[FrameStatus] = [
            FrameStatus(
                frame_idx=i,
                frame_type=scene_plan.frame_types[i],
                status="pending",
            )
            for i in range(num_frames)
        ]

        # Semaphore to limit concurrent Imagen calls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGEN_CALLS)

        # Fire all 32 tasks concurrently
        tasks = [
            self._generate_single_frame(
                frame_idx=i,
                prompt=scene_plan.prompts[i],
                frame_status=frame_statuses[i],
                project_id=project_id,
                room_id=room_id,
                semaphore=semaphore,
            )
            for i in range(num_frames)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any unexpected exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Frame %d raised unexpected exception: %s", i, result
                )
                frame_statuses[i].status = "failed"
                frame_statuses[i].error_message = str(result)

        # After Frame 0 completes: publish preview event
        if frame_statuses[0].status == "complete" and frame_statuses[0].gcs_url:
            preview_url = self.storage.get_signed_url(frame_statuses[0].gcs_url)
            logger.info(
                "Frame 0 preview ready — project=%s, room=%s, url=%s",
                project_id, room_id, preview_url[:100],
            )

        # Summary logging
        complete_count = sum(1 for fs in frame_statuses if fs.status == "complete")
        failed_count = sum(1 for fs in frame_statuses if fs.status == "failed")
        logger.info(
            "Generation complete — %d/%d succeeded, %d failed",
            complete_count, num_frames, failed_count,
        )

        return frame_statuses

    # ------------------------------------------------------------------
    # Single frame generation with retry
    # ------------------------------------------------------------------

    async def _generate_single_frame(
        self,
        frame_idx: int,
        prompt: str,
        frame_status: FrameStatus,
        project_id: str,
        room_id: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Generate a single frame with retries and exponential backoff.

        Retry logic:
        1. Up to MAX_REGENERATION_ATTEMPTS tries with exponential backoff.
        2. On 3rd failure: soften prompt and retry once more.
        3. Upload successful PNG to GCS.
        """
        async with semaphore:
            frame_status.status = "generating"
            gcs_path = GCS_PATH_FRAMES_RAW.format(
                project_id=project_id, room_id=room_id, n=frame_idx
            )

            logger.info(
                "Generating frame %d (type=%s, prompt=%.80s...)",
                frame_idx, frame_status.frame_type, prompt,
            )

            # --- Attempts 1 through MAX_REGENERATION_ATTEMPTS ---
            last_error: Exception | None = None
            for attempt in range(1, MAX_REGENERATION_ATTEMPTS + 1):
                try:
                    frame_status.attempts = attempt
                    image_bytes = await self.imagen.generate_frame(prompt=prompt)

                    # Upload to GCS
                    await self.storage.upload_bytes(
                        data=image_bytes,
                        gcs_path=gcs_path,
                        content_type="image/png",
                    )

                    frame_status.status = "complete"
                    frame_status.gcs_url = gcs_path
                    frame_status.completed_at = datetime.utcnow()

                    logger.info(
                        "Frame %d generated successfully (attempt %d) -> %s",
                        frame_idx, attempt, gcs_path,
                    )
                    return

                except Exception as exc:
                    last_error = exc
                    wait = 2.0 ** attempt
                    logger.warning(
                        "Frame %d attempt %d/%d failed: %s. Retrying in %.1fs...",
                        frame_idx, attempt, MAX_REGENERATION_ATTEMPTS, exc, wait,
                    )
                    frame_status.status = "retrying"
                    if attempt < MAX_REGENERATION_ATTEMPTS:
                        await asyncio.sleep(wait)

            # --- All standard attempts exhausted: soften prompt and try once more ---
            logger.warning(
                "Frame %d: all %d attempts failed. Trying softened prompt...",
                frame_idx, MAX_REGENERATION_ATTEMPTS,
            )

            softened_prompt = _soften_prompt(prompt)
            frame_status.attempts += 1

            try:
                image_bytes = await self.imagen.generate_frame(prompt=softened_prompt)

                await self.storage.upload_bytes(
                    data=image_bytes,
                    gcs_path=gcs_path,
                    content_type="image/png",
                )

                frame_status.status = "complete"
                frame_status.gcs_url = gcs_path
                frame_status.completed_at = datetime.utcnow()

                logger.info(
                    "Frame %d generated with softened prompt -> %s",
                    frame_idx, gcs_path,
                )
                return

            except Exception as exc:
                logger.error(
                    "Frame %d: softened prompt also failed: %s. Marking as failed.",
                    frame_idx, exc,
                )
                frame_status.status = "failed"
                frame_status.error_message = (
                    f"Failed after {MAX_REGENERATION_ATTEMPTS} attempts + 1 softened: "
                    f"{last_error} / {exc}"
                )
