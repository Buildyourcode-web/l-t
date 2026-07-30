"""
Camera status API route.

GET /api/cameras — Returns live status for all cameras.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.camera.manager import camera_manager

router = APIRouter(prefix="/api", tags=["cameras"])


@router.get("/cameras")
async def get_cameras():
    """Return live status for all configured cameras."""
    statuses = camera_manager.get_camera_statuses()
    return {
        "cameras": statuses,
        "total": camera_manager.total_cameras,
        "online": camera_manager.get_online_count(),
    }
