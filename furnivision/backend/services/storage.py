"""FurniVision AI — Google Cloud Storage service."""

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from google.cloud import storage as gcs

from config import GCS_BUCKET_NAME, GCS_SIGNED_URL_EXPIRY_HOURS

logger = logging.getLogger(__name__)


class StorageService:
    """Wrapper around Google Cloud Storage for upload, download, and signed URL generation."""

    def __init__(self) -> None:
        try:
            self._client = gcs.Client()
            self._bucket = self._client.bucket(GCS_BUCKET_NAME)
            logger.info("StorageService initialised — bucket=%s", GCS_BUCKET_NAME)
        except Exception:
            logger.exception("Failed to initialise GCS client")
            raise

    # ------------------------------------------------------------------
    # Upload helpers
    # ------------------------------------------------------------------

    async def upload_file(self, local_path: str, gcs_path: str) -> str:
        """Upload a local file to GCS. Returns the gcs_path on success."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._upload_file_sync, local_path, gcs_path)
            logger.info("Uploaded %s -> gs://%s/%s", local_path, GCS_BUCKET_NAME, gcs_path)
            return gcs_path
        except Exception:
            logger.exception("Upload failed for %s -> %s", local_path, gcs_path)
            raise

    def _upload_file_sync(self, local_path: str, gcs_path: str) -> None:
        blob = self._bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)

    async def upload_bytes(self, data: bytes, gcs_path: str, content_type: str = "application/octet-stream") -> str:
        """Upload raw bytes to GCS. Returns the gcs_path on success."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._upload_bytes_sync, data, gcs_path, content_type)
            logger.info(
                "Uploaded %d bytes -> gs://%s/%s (content_type=%s)",
                len(data), GCS_BUCKET_NAME, gcs_path, content_type,
            )
            return gcs_path
        except Exception:
            logger.exception("Byte upload failed for %s", gcs_path)
            raise

    def _upload_bytes_sync(self, data: bytes, gcs_path: str, content_type: str) -> None:
        blob = self._bucket.blob(gcs_path)
        blob.upload_from_string(data, content_type=content_type)

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------

    async def download_file(self, gcs_path: str, local_path: str) -> str:
        """Download a GCS object to a local file. Returns *local_path*."""
        loop = asyncio.get_running_loop()
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            await loop.run_in_executor(None, self._download_file_sync, gcs_path, local_path)
            logger.info("Downloaded gs://%s/%s -> %s", GCS_BUCKET_NAME, gcs_path, local_path)
            return local_path
        except Exception:
            logger.exception("Download failed for %s -> %s", gcs_path, local_path)
            raise

    def _download_file_sync(self, gcs_path: str, local_path: str) -> None:
        blob = self._bucket.blob(gcs_path)
        blob.download_to_filename(local_path)

    async def download_bytes(self, gcs_path: str) -> bytes:
        """Download a GCS object and return its contents as bytes."""
        loop = asyncio.get_running_loop()
        try:
            data: bytes = await loop.run_in_executor(None, self._download_bytes_sync, gcs_path)
            logger.info("Downloaded %d bytes from gs://%s/%s", len(data), GCS_BUCKET_NAME, gcs_path)
            return data
        except Exception:
            logger.exception("Byte download failed for %s", gcs_path)
            raise

    def _download_bytes_sync(self, gcs_path: str) -> bytes:
        blob = self._bucket.blob(gcs_path)
        return blob.download_as_bytes()

    # ------------------------------------------------------------------
    # Signed URL
    # ------------------------------------------------------------------

    def get_signed_url(self, gcs_path: str, expiry_hours: int | None = None) -> str:
        """Generate a signed URL for the given GCS object."""
        hours = expiry_hours if expiry_hours is not None else GCS_SIGNED_URL_EXPIRY_HOURS
        try:
            blob = self._bucket.blob(gcs_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=hours),
                method="GET",
            )
            logger.debug("Signed URL generated for %s (expiry=%dh)", gcs_path, hours)
            return url
        except Exception:
            logger.exception("Signed URL generation failed for %s", gcs_path)
            raise

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    async def list_files(self, prefix: str) -> list[str]:
        """List all blob names under *prefix*."""
        loop = asyncio.get_running_loop()
        try:
            names: list[str] = await loop.run_in_executor(None, self._list_files_sync, prefix)
            logger.info("Listed %d files under prefix '%s'", len(names), prefix)
            return names
        except Exception:
            logger.exception("List files failed for prefix '%s'", prefix)
            raise

    def _list_files_sync(self, prefix: str) -> list[str]:
        blobs = self._client.list_blobs(self._bucket, prefix=prefix)
        return [blob.name for blob in blobs]
