"""
Reports API route.

GET /api/reports/download/pdf?date=YYYY-MM-DD
GET /api/reports/download/excel?date=YYYY-MM-DD
POST /api/reports/generate?date=YYYY-MM-DD  — trigger generation on demand
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.scheduler import generate_daily_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/download/pdf")
async def download_pdf(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    """Download the PDF report for a given date."""
    report_path = Path(settings.REPORTS_DIR) / str(report_date) / "report.pdf"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF report not found for {report_date}")
    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=f"safety_report_{report_date}.pdf",
    )


@router.get("/download/excel")
async def download_excel(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    """Download the Excel report for a given date."""
    report_path = Path(settings.REPORTS_DIR) / str(report_date) / "report.xlsx"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Excel report not found for {report_date}")
    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"safety_report_{report_date}.xlsx",
    )


@router.post("/generate")
async def trigger_report_generation(
    background_tasks: BackgroundTasks,
    report_date: Optional[date] = Query(None, description="Date to generate (default: yesterday)"),
):
    """Trigger on-demand report generation (runs in background)."""
    background_tasks.add_task(generate_daily_report, report_date)
    return {
        "message": f"Report generation started for {report_date or 'yesterday'}",
        "status": "queued",
    }


@router.get("/list")
async def list_reports():
    """List all available report dates."""
    reports_dir = Path(settings.REPORTS_DIR)
    if not reports_dir.exists():
        return {"reports": []}

    available = []
    for day_dir in sorted(reports_dir.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        try:
            d = date.fromisoformat(day_dir.name)
            has_pdf = (day_dir / "report.pdf").exists()
            has_xlsx = (day_dir / "report.xlsx").exists()
            if has_pdf or has_xlsx:
                available.append({"date": str(d), "has_pdf": has_pdf, "has_xlsx": has_xlsx})
        except ValueError:
            pass

    return {"reports": available}
