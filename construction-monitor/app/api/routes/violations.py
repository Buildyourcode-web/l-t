"""
Violations API route.

GET /api/violations
    Supports filters: camera_id, date_from, date_to, violation_type
    Supports pagination: page, page_size
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.database.crud import get_violations

router = APIRouter(prefix="/api", tags=["violations"])


@router.get("/violations")
async def list_violations(
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    date_from: Optional[date] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="To date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Paginated violation list with optional filters."""
    violations, total = await get_violations(
        db,
        camera_id=camera_id,
        violation_type=violation_type,
        from_date=date_from,
        to_date=date_to,
        page=page,
        page_size=page_size,
    )
    return {
        "violations": [v.to_dict() for v in violations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
