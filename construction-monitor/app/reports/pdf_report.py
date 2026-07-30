"""
PDF Report Generator using ReportLab.

Generates a daily violation report PDF with:
- Summary statistics section
- Per-violation table with camera, time, type, track ID
- Embedded thumbnails (if screenshots exist)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "api")


def generate_pdf(
    violations: list,
    output_path: str,
    report_date: date,
) -> None:
    """
    Generate a PDF report for the given violations.

    Args:
        violations: List of Violation ORM objects
        output_path: Absolute path where the PDF will be saved
        report_date: The date this report covers
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
        spaceBefore=16,
    )
    body_style = styles["Normal"]

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("🏗️ Construction Site AI Monitor", title_style))
    story.append(Paragraph(f"Daily Safety Violation Report — {report_date.strftime('%B %d, %Y')}", subtitle_style))
    story.append(Spacer(1, 0.5 * cm))

    # ── Summary Statistics ────────────────────────────────────────────────
    story.append(Paragraph("Summary", section_style))

    helmet_count = sum(1 for v in violations if v.violation_type == "no_helmet")
    vest_count = sum(1 for v in violations if v.violation_type == "no_vest")
    fire_count = sum(1 for v in violations if v.violation_type == "fire")
    total = len(violations)

    summary_data = [
        ["Metric", "Count"],
        ["Total Violations", str(total)],
        ["Helmet Violations", str(helmet_count)],
        ["Vest Violations", str(vest_count)],
        ["Fire Alerts", str(fire_count)],
    ]

    summary_table = Table(summary_data, colWidths=[8 * cm, 4 * cm])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Violations Table ──────────────────────────────────────────────────
    story.append(Paragraph("Violation Details", section_style))

    headers = ["#", "Time", "Camera", "Violation", "Track ID", "Confidence", "Screenshot"]
    col_widths = [1*cm, 3*cm, 5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 4*cm]

    table_data = [headers]
    for idx, v in enumerate(violations, start=1):
        time_str = v.detected_at.strftime("%H:%M:%S") if v.detected_at else "—"
        conf_str = f"{v.confidence * 100:.1f}%"

        # Add thumbnail if image exists and fits
        img_cell = "—"
        if v.image_path:
            img_full = Path(settings.SCREENSHOT_DIR).parent / v.image_path
            if img_full.exists():
                try:
                    img = Image(str(img_full), width=3.5*cm, height=2.5*cm)
                    img_cell = img
                except Exception:
                    img_cell = "[img]"

        table_data.append([
            str(idx),
            time_str,
            v.camera_name,
            v.violation_type.replace("_", " ").upper(),
            v.track_id,
            conf_str,
            img_cell,
        ])

    detail_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    detail_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWHEIGHT", (0, 1), (-1, -1), 60),
        ])
    )
    story.append(detail_table)

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        f"Generated by Construction Site AI Monitor | {report_date}",
        ParagraphStyle("footer", parent=body_style, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    logger.info("PDF report generated: %s (%d violations)", output_path, total)
