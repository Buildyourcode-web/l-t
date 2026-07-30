"""
Latest images API route.

GET /api/latest-images — Returns the most recent N violation screenshots.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.database.crud import get_latest_images

router = APIRouter(prefix="/api", tags=["images"])


@router.get("/latest-images")
async def get_latest_images_endpoint(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Return the most recent violation images."""
    images = await get_latest_images(db, limit=limit)
    return {"images": [v.to_dict() for v in images]}
