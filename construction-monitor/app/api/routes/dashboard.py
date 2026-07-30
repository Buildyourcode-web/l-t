"""
Dashboard API route.

GET /api/dashboard
    Returns today's violation counts, camera status summary, and recent images.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.camera.manager import camera_manager
from app.database.crud import get_today_summary, get_latest_images

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_session)):
    """Return today's summary statistics and camera status."""
    summary = await get_today_summary(db)
    camera_statuses = camera_manager.get_camera_statuses()
    latest_images = await get_latest_images(db, limit=20)

    return {
        "summary": summary,
        "cameras": {
            "total": camera_manager.total_cameras,
            "online": camera_manager.get_online_count(),
            "statuses": camera_statuses,
        },
        "latest_images": [v.to_dict() for v in latest_images],
    }
