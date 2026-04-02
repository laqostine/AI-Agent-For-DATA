"""FurniVision AI — Image processing utilities (colour grading, resizing, etc.)."""

import io
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    """CPU-based image processing using OpenCV, NumPy, and Pillow."""

    # ------------------------------------------------------------------
    # Histogram matching in LAB colour space
    # ------------------------------------------------------------------

    def match_histograms(
        self,
        source_img: np.ndarray,
        reference_img: np.ndarray,
    ) -> np.ndarray:
        """Match the colour histogram of *source_img* to *reference_img*.

        Both images are expected in BGR format (OpenCV default).
        The matching is performed independently on each channel of the
        CIE-LAB colour space so that luminance and chrominance are
        handled separately.

        Returns the colour-matched image in BGR format.
        """
        src_lab = cv2.cvtColor(source_img, cv2.COLOR_BGR2LAB).astype(np.float64)
        ref_lab = cv2.cvtColor(reference_img, cv2.COLOR_BGR2LAB).astype(np.float64)

        matched_channels: list[np.ndarray] = []
        for ch in range(3):
            src_ch = src_lab[:, :, ch]
            ref_ch = ref_lab[:, :, ch]
            matched_ch = self._match_channel(src_ch, ref_ch)
            matched_channels.append(matched_ch)

        matched_lab = np.stack(matched_channels, axis=-1).clip(0, 255).astype(np.uint8)
        result = cv2.cvtColor(matched_lab, cv2.COLOR_LAB2BGR)

        logger.debug(
            "Histogram matched: source %s -> reference %s",
            source_img.shape, reference_img.shape,
        )
        return result

    @staticmethod
    def _match_channel(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """Match the histogram of a single channel using CDF mapping."""
        src_vals = source.flatten()
        ref_vals = reference.flatten()

        # Compute CDFs
        src_counts, src_bins = np.histogram(src_vals, bins=256, range=(0, 256))
        ref_counts, ref_bins = np.histogram(ref_vals, bins=256, range=(0, 256))

        src_cdf = np.cumsum(src_counts).astype(np.float64)
        src_cdf /= src_cdf[-1]

        ref_cdf = np.cumsum(ref_counts).astype(np.float64)
        ref_cdf /= ref_cdf[-1]

        # Build look-up table: for each source intensity, find the reference
        # intensity whose CDF value is closest.
        lut = np.interp(src_cdf, ref_cdf, np.arange(256))

        # Apply LUT
        matched = lut[source.astype(np.intp).clip(0, 255)]
        return matched

    # ------------------------------------------------------------------
    # Vignette effect
    # ------------------------------------------------------------------

    def apply_vignette(
        self,
        img: np.ndarray,
        strength: float = 0.3,
    ) -> np.ndarray:
        """Apply a radial vignette darkening to *img* (BGR).

        *strength* controls how dark the corners become (0 = no effect,
        1 = black corners).
        """
        rows, cols = img.shape[:2]

        # Build a 2-D Gaussian-like mask centred on the image
        x = np.linspace(-1.0, 1.0, cols)
        y = np.linspace(-1.0, 1.0, rows)
        xv, yv = np.meshgrid(x, y)

        # Radial distance from centre, normalised so corners ≈ 1.0
        radius = np.sqrt(xv ** 2 + yv ** 2)
        radius = radius / radius.max()

        # Vignette mask: 1.0 in centre, (1 - strength) at corners
        mask = 1.0 - strength * (radius ** 2)
        mask = np.clip(mask, 0.0, 1.0)

        # Apply mask to each channel
        if img.ndim == 3:
            mask = mask[:, :, np.newaxis]

        result = (img.astype(np.float64) * mask).clip(0, 255).astype(np.uint8)

        logger.debug(
            "Vignette applied (strength=%.2f) to %dx%d image",
            strength, cols, rows,
        )
        return result

    # ------------------------------------------------------------------
    # Resizing
    # ------------------------------------------------------------------

    def resize_for_output(
        self,
        img: np.ndarray,
        max_width: int = 1920,
    ) -> np.ndarray:
        """Down-scale *img* so its width does not exceed *max_width*.

        Maintains aspect ratio.  If the image is already smaller, it is
        returned unchanged.
        """
        h, w = img.shape[:2]
        if w <= max_width:
            logger.debug("Image %dx%d already within max_width=%d", w, h, max_width)
            return img

        scale = max_width / w
        new_w = max_width
        new_h = int(h * scale)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.debug("Resized %dx%d -> %dx%d (max_width=%d)", w, h, new_w, new_h, max_width)
        return resized

    # ------------------------------------------------------------------
    # Format conversion
    # ------------------------------------------------------------------

    def to_webp_bytes(self, img: np.ndarray, quality: int = 90) -> bytes:
        """Encode a BGR numpy image to WebP bytes via Pillow.

        Returns the raw WebP byte string.
        """
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        buf = io.BytesIO()
        pil_img.save(buf, format="WEBP", quality=quality)
        data = buf.getvalue()
        logger.debug("Encoded WebP: %d bytes (quality=%d)", len(data), quality)
        return data

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def load_image(self, path: str) -> np.ndarray:
        """Load an image from *path* as a BGR numpy array.

        Raises ``FileNotFoundError`` if the path does not exist and
        ``ValueError`` if OpenCV cannot decode the file.
        """
        path = str(Path(path).resolve())
        if not Path(path).is_file():
            raise FileNotFoundError(f"Image not found: {path}")

        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"OpenCV could not decode image: {path}")

        logger.debug("Loaded image %s (%dx%d)", path, img.shape[1], img.shape[0])
        return img

    def save_image(self, img: np.ndarray, path: str) -> None:
        """Save a BGR numpy array to *path*.

        The parent directory is created if it does not exist.  The format
        is inferred from the file extension by OpenCV.
        """
        path = str(Path(path).resolve())
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        success = cv2.imwrite(path, img)
        if not success:
            raise IOError(f"Failed to write image to {path}")

        logger.debug("Saved image to %s", path)
