"""FurniVision AI — PDF report generation with ReportLab."""

import logging
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------

_BRAND_COLOR = colors.HexColor("#1A73E8")
_DARK_TEXT = colors.HexColor("#202124")
_LIGHT_BG = colors.HexColor("#F8F9FA")

_styles = getSampleStyleSheet()

_TITLE_STYLE = ParagraphStyle(
    "FVTitle",
    parent=_styles["Title"],
    fontSize=28,
    leading=34,
    textColor=_BRAND_COLOR,
    spaceAfter=12,
)

_HEADING_STYLE = ParagraphStyle(
    "FVHeading",
    parent=_styles["Heading1"],
    fontSize=18,
    leading=22,
    textColor=_BRAND_COLOR,
    spaceBefore=18,
    spaceAfter=8,
)

_SUBHEADING_STYLE = ParagraphStyle(
    "FVSubheading",
    parent=_styles["Heading2"],
    fontSize=14,
    leading=18,
    textColor=_DARK_TEXT,
    spaceBefore=12,
    spaceAfter=6,
)

_BODY_STYLE = ParagraphStyle(
    "FVBody",
    parent=_styles["BodyText"],
    fontSize=10,
    leading=14,
    textColor=_DARK_TEXT,
    spaceAfter=6,
)

_SMALL_STYLE = ParagraphStyle(
    "FVSmall",
    parent=_styles["BodyText"],
    fontSize=8,
    leading=10,
    textColor=colors.grey,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _safe_image(path: str, width: float, height: float) -> RLImage | Paragraph:
    """Return a ReportLab Image if *path* exists, otherwise a placeholder paragraph."""
    if path and os.path.isfile(path):
        try:
            return RLImage(path, width=width, height=height)
        except Exception:
            logger.warning("Could not load image for report: %s", path)
    return Paragraph(f"<i>[Image not available: {path}]</i>", _SMALL_STYLE)


def _stat_table(stats: dict) -> Table:
    """Build a two-column key/value table from a stats dict."""
    data = [["Metric", "Value"]]
    for key, value in stats.items():
        label = str(key).replace("_", " ").title()
        data.append([label, str(value)])

    table = Table(data, colWidths=[6 * cm, 8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BRAND_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _footer(canvas, doc):
    """Draw a simple page footer with page number and timestamp."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    page_text = f"Page {doc.page}  |  FurniVision AI  |  Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, page_text)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Builds PDF reports for individual rooms and full projects."""

    # ------------------------------------------------------------------
    # Single-room report
    # ------------------------------------------------------------------

    def generate_room_report(
        self,
        room_label: str,
        hero_images: list[str],
        stats: dict,
        output_path: str,
    ) -> str:
        """Generate a single-room PDF report.

        Parameters
        ----------
        room_label:
            Human-readable room name (e.g. "Living Room A").
        hero_images:
            List of file paths to hero render images.
        stats:
            Dictionary of QC / pipeline stats to display.
        output_path:
            Where to write the PDF.

        Returns the *output_path* on success.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info("Generating room report for '%s' -> %s", room_label, output_path)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        story: list = []

        # Title
        story.append(Paragraph("FurniVision AI — Room Report", _TITLE_STYLE))
        story.append(Spacer(1, 6 * mm))

        # Room heading
        story.append(Paragraph(room_label, _HEADING_STYLE))
        story.append(Spacer(1, 4 * mm))

        # Hero images
        if hero_images:
            story.append(Paragraph("Hero Renders", _SUBHEADING_STYLE))
            story.append(Spacer(1, 2 * mm))

            img_width = 16 * cm
            img_height = 10 * cm

            for idx, img_path in enumerate(hero_images):
                story.append(
                    Paragraph(f"<b>Hero {idx + 1}</b>", _BODY_STYLE)
                )
                story.append(_safe_image(img_path, img_width, img_height))
                story.append(Spacer(1, 4 * mm))

                # Page break between images to avoid overflow
                if idx < len(hero_images) - 1:
                    story.append(PageBreak())
        else:
            story.append(
                Paragraph("<i>No hero images available.</i>", _BODY_STYLE)
            )

        # Stats section
        story.append(PageBreak())
        story.append(Paragraph("Quality &amp; Pipeline Statistics", _HEADING_STYLE))
        story.append(Spacer(1, 4 * mm))

        if stats:
            story.append(_stat_table(stats))
        else:
            story.append(Paragraph("<i>No statistics available.</i>", _BODY_STYLE))

        story.append(Spacer(1, 10 * mm))
        story.append(
            Paragraph(
                f"Report generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                _SMALL_STYLE,
            )
        )

        try:
            doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
            logger.info("Room report written: %s", output_path)
        except Exception:
            logger.exception("Failed to build room report PDF")
            raise

        return output_path

    # ------------------------------------------------------------------
    # Project-level master report
    # ------------------------------------------------------------------

    def generate_project_report(
        self,
        project_name: str,
        rooms: list[dict],
        output_path: str,
    ) -> str:
        """Generate a multi-room project report PDF.

        Parameters
        ----------
        project_name:
            Display name for the project.
        rooms:
            List of dicts, each containing:
            - ``label`` (str): room display name
            - ``hero_images`` (list[str]): paths to hero renders
            - ``stats`` (dict): QC / pipeline stats
        output_path:
            Where to write the PDF.

        Returns the *output_path* on success.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Generating project report '%s' (%d rooms) -> %s",
            project_name, len(rooms), output_path,
        )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        story: list = []

        # ---- Cover page ----
        story.append(Spacer(1, 6 * cm))
        story.append(Paragraph("FurniVision AI", _TITLE_STYLE))
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(project_name, _HEADING_STYLE))
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                f"Project Report &bull; {len(rooms)} Room{'s' if len(rooms) != 1 else ''}",
                _BODY_STYLE,
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                _SMALL_STYLE,
            )
        )

        # ---- Table of contents ----
        story.append(PageBreak())
        story.append(Paragraph("Contents", _HEADING_STYLE))
        story.append(Spacer(1, 4 * mm))
        for idx, room in enumerate(rooms, 1):
            label = room.get("label", f"Room {idx}")
            story.append(
                Paragraph(f"{idx}. {label}", _BODY_STYLE)
            )
        story.append(Spacer(1, 6 * mm))

        # ---- Per-room sections ----
        img_width = 16 * cm
        img_height = 10 * cm

        for idx, room in enumerate(rooms, 1):
            label = room.get("label", f"Room {idx}")
            hero_images = room.get("hero_images", [])
            stats = room.get("stats", {})

            story.append(PageBreak())
            story.append(Paragraph(f"{idx}. {label}", _HEADING_STYLE))
            story.append(Spacer(1, 4 * mm))

            # Hero images
            if hero_images:
                story.append(Paragraph("Hero Renders", _SUBHEADING_STYLE))
                for img_idx, img_path in enumerate(hero_images):
                    story.append(
                        Paragraph(f"<b>Hero {img_idx + 1}</b>", _BODY_STYLE)
                    )
                    story.append(_safe_image(img_path, img_width, img_height))
                    story.append(Spacer(1, 4 * mm))
                    if img_idx < len(hero_images) - 1:
                        story.append(PageBreak())
            else:
                story.append(
                    Paragraph("<i>No hero images for this room.</i>", _BODY_STYLE)
                )

            # Stats
            story.append(PageBreak())
            story.append(
                Paragraph(f"{label} — Statistics", _SUBHEADING_STYLE)
            )
            story.append(Spacer(1, 2 * mm))

            if stats:
                story.append(_stat_table(stats))
            else:
                story.append(
                    Paragraph("<i>No statistics available.</i>", _BODY_STYLE)
                )

        # ---- Final page ----
        story.append(PageBreak())
        story.append(Spacer(1, 6 * cm))
        story.append(
            Paragraph("End of Report", _HEADING_STYLE)
        )
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                "This report was generated automatically by the FurniVision AI pipeline.",
                _BODY_STYLE,
            )
        )

        try:
            doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
            logger.info("Project report written: %s", output_path)
        except Exception:
            logger.exception("Failed to build project report PDF")
            raise

        return output_path
