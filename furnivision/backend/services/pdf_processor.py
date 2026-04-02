"""FurniVision AI — PDF processing service (page rendering & image extraction)."""

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Utilities for converting PDF pages to images and extracting embedded images."""

    # ------------------------------------------------------------------
    # Page-level rendering via pdf2image (poppler)
    # ------------------------------------------------------------------

    def convert_to_images(self, pdf_path: str, dpi: int = 300) -> list[bytes]:
        """Render every page of *pdf_path* as a PNG image at the given DPI.

        Returns a list of PNG byte strings, one per page.
        """
        pdf_path = str(Path(pdf_path).resolve())
        logger.info("Converting PDF to images: %s (dpi=%d)", pdf_path, dpi)

        try:
            pil_images: list[Image.Image] = convert_from_path(pdf_path, dpi=dpi)
        except Exception:
            logger.exception("pdf2image conversion failed for %s", pdf_path)
            raise

        png_bytes_list: list[bytes] = []
        for idx, img in enumerate(pil_images):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            page_bytes = buf.getvalue()
            png_bytes_list.append(page_bytes)
            logger.debug(
                "Page %d rendered: %d x %d, %d bytes",
                idx + 1, img.width, img.height, len(page_bytes),
            )

        logger.info(
            "Converted %d pages from %s (%d total bytes)",
            len(png_bytes_list),
            pdf_path,
            sum(len(b) for b in png_bytes_list),
        )
        return png_bytes_list

    # ------------------------------------------------------------------
    # Embedded image extraction via PyMuPDF
    # ------------------------------------------------------------------

    def extract_embedded_images(self, pdf_path: str) -> list[bytes]:
        """Extract all embedded raster images from the PDF.

        Returns a list of PNG byte strings.  Vector drawings are *not*
        included — only images referenced via the ``/XObject`` stream.
        """
        pdf_path = str(Path(pdf_path).resolve())
        logger.info("Extracting embedded images from %s", pdf_path)

        extracted: list[bytes] = []

        try:
            doc = fitz.open(pdf_path)
        except Exception:
            logger.exception("Failed to open PDF with PyMuPDF: %s", pdf_path)
            raise

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if base_image is None:
                            logger.debug(
                                "Page %d, xref %d: extract_image returned None",
                                page_num + 1, xref,
                            )
                            continue

                        image_bytes = base_image["image"]
                        image_ext = base_image.get("ext", "png")

                        # Normalise to PNG if the embedded format is different
                        if image_ext.lower() != "png":
                            pil_img = Image.open(io.BytesIO(image_bytes))
                            buf = io.BytesIO()
                            pil_img.save(buf, format="PNG")
                            image_bytes = buf.getvalue()

                        extracted.append(image_bytes)
                        logger.debug(
                            "Page %d, img %d (xref=%d): extracted %d bytes (orig ext=%s)",
                            page_num + 1, img_idx, xref, len(image_bytes), image_ext,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to extract image xref=%d on page %d",
                            xref, page_num + 1,
                            exc_info=True,
                        )
        finally:
            doc.close()

        logger.info("Extracted %d embedded images from %s", len(extracted), pdf_path)
        return extracted

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    def get_page_count(self, pdf_path: str) -> int:
        """Return the number of pages in the PDF."""
        pdf_path = str(Path(pdf_path).resolve())
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            logger.info("Page count for %s: %d", pdf_path, count)
            return count
        except Exception:
            logger.exception("Failed to get page count for %s", pdf_path)
            raise
