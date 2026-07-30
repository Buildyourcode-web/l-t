"""
APScheduler service for:
1. Daily PDF + Excel report generation (runs at midnight)
2. Data retention cleanup (deletes screenshots/reports older than N days)
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "api")


async def generate_daily_report(target_date: Optional[date] = None) -> None:
    """
    Generate PDF and Excel reports for target_date (default: yesterday).
    Saves to reports/{YYYY-MM-DD}/report.pdf and report.xlsx
    """
    from app.database.session import get_session_factory
    from app.database.crud import get_violations_for_date
    from app.reports.pdf_report import generate_pdf
    from app.reports.excel_report import generate_excel

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info("Generating daily report for %s", target_date)

    factory = get_session_factory()
    async with factory() as session:
        violations = await get_violations_for_date(session, target_date)

    if not violations:
        logger.info("No violations found for %s — skipping report", target_date)
        return

    # Create output directory
    output_dir = Path(settings.REPORTS_DIR) / str(target_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate PDF
    pdf_path = output_dir / "report.pdf"
    try:
        generate_pdf(violations, str(pdf_path), target_date)
        logger.info("PDF report saved: %s", pdf_path)
    except Exception as e:
        logger.error("PDF generation failed: %s", e)

    # Generate Excel
    xlsx_path = output_dir / "report.xlsx"
    try:
        generate_excel(violations, str(xlsx_path), target_date)
        logger.info("Excel report saved: %s", xlsx_path)
    except Exception as e:
        logger.error("Excel generation failed: %s", e)


async def run_retention_cleanup() -> None:
    """
    Delete screenshots and reports older than configured retention days.
    Runs daily at 01:00 AM.
    """
    cutoff_screenshots = date.today() - timedelta(days=settings.SCREENSHOTS_RETENTION_DAYS)
    cutoff_reports = date.today() - timedelta(days=settings.REPORTS_RETENTION_DAYS)

    def cleanup_dir(base_dir: str, cutoff: date, label: str) -> None:
        base = Path(base_dir)
        if not base.exists():
            return
        removed = 0
        for day_dir in base.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                dir_date = date.fromisoformat(day_dir.name)
                if dir_date < cutoff:
                    shutil.rmtree(day_dir)
                    removed += 1
            except ValueError:
                pass  # non-date directory
        if removed:
            logger.info("Retention cleanup: removed %d %s directories older than %s", removed, label, cutoff)

    cleanup_dir(settings.SCREENSHOT_DIR, cutoff_screenshots, "screenshot")
    cleanup_dir(settings.REPORTS_DIR, cutoff_reports, "report")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Daily report at midnight UTC
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=0, minute=0),
        id="daily_report",
        name="Daily Report Generator",
        misfire_grace_time=3600,  # run even if missed by up to 1 hour
        replace_existing=True,
    )

    # Retention cleanup at 01:00 AM UTC
    scheduler.add_job(
        run_retention_cleanup,
        CronTrigger(hour=1, minute=0),
        id="retention_cleanup",
        name="Retention Cleanup",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    return scheduler
