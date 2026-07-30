"""
System health API route.

GET /api/health — Returns CPU, RAM, GPU, FPS, camera metrics.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.health_service import health_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def get_system_health():
    """Return real-time system metrics."""
    return health_service.get_metrics()
