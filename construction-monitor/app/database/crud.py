"""
CRUD helpers for violations and camera_status tables.
All functions accept an AsyncSession and return typed objects.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CameraStatus, Violation


# ── Violations ────────────────────────────────────────────────────────────────

async def save_violation(
    db: AsyncSession,
    *,
    camera_id: int,
    camera_name: str,
    track_id: str,
    violation_type: str,
    confidence: float,
    image_path: Optional[str] = None,
) -> Violation:
    """Insert a new violation record and return it."""
    violation = Violation(
        camera_id=camera_id,
        camera_name=camera_name,
        track_id=str(track_id),
        violation_type=violation_type,
        confidence=confidence,
        image_path=image_path,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(violation)
    await db.flush()  # get auto-generated id before commit
    return violation


async def get_violations(
    db: AsyncSession,
    *,
    camera_id: Optional[int] = None,
    violation_type: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[List[Violation], int]:
    """Paginated violation query with optional filters."""
    stmt = select(Violation).order_by(Violation.detected_at.desc())

    if camera_id is not None:
        stmt = stmt.where(Violation.camera_id == camera_id)
    if violation_type:
        stmt = stmt.where(Violation.violation_type == violation_type)
    if from_date:
        stmt = stmt.where(func.date(Violation.detected_at) >= from_date)
    if to_date:
        stmt = stmt.where(func.date(Violation.detected_at) <= to_date)

    # Count total before paging
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    results = (await db.execute(stmt)).scalars().all()
    return list(results), total


async def get_today_summary(db: AsyncSession) -> Dict:
    """Return today's violation counts grouped by type."""
    today = date.today()
    stmt = (
        select(Violation.violation_type, func.count(Violation.id).label("cnt"))
        .where(func.date(Violation.detected_at) == today)
        .group_by(Violation.violation_type)
    )
    rows = (await db.execute(stmt)).all()
    counts = {row.violation_type: row.cnt for row in rows}
    return {
        "helmet": counts.get("no_helmet", 0),
        "vest": counts.get("no_vest", 0),
        "fire": counts.get("fire", 0),
        "total": sum(counts.values()),
        "date": today.isoformat(),
    }


async def get_latest_images(
    db: AsyncSession, limit: int = 20
) -> List[Violation]:
    """Return the most recent N violations that have screenshots."""
    stmt = (
        select(Violation)
        .where(Violation.image_path.isnot(None))
        .order_by(Violation.detected_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_violations_for_date(
    db: AsyncSession, target_date: date
) -> List[Violation]:
    """Fetch all violations for a specific date (for reports)."""
    stmt = (
        select(Violation)
        .where(func.date(Violation.detected_at) == target_date)
        .order_by(Violation.camera_id, Violation.detected_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_violations_before(
    db: AsyncSession, before_date: date
) -> int:
    """Delete violations older than given date (retention policy)."""
    stmt = delete(Violation).where(
        func.date(Violation.detected_at) < before_date
    )
    result = await db.execute(stmt)
    return result.rowcount


# ── Camera Status ─────────────────────────────────────────────────────────────

async def upsert_camera_status(
    db: AsyncSession,
    *,
    camera_id: int,
    name: str,
    online: bool,
    fps: float = 0.0,
    rtsp_url: Optional[str] = None,
    last_frame_at: Optional[datetime] = None,
) -> None:
    """Insert or update a camera status row."""
    stmt = pg_insert(CameraStatus).values(
        camera_id=camera_id,
        name=name,
        online=online,
        fps=fps,
        rtsp_url=rtsp_url,
        last_frame_at=last_frame_at or datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["camera_id"],
        set_={
            "online": online,
            "fps": fps,
            "last_frame_at": last_frame_at or datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)


async def get_all_camera_statuses(db: AsyncSession) -> List[CameraStatus]:
    """Return status rows for all cameras."""
    stmt = select(CameraStatus).order_by(CameraStatus.camera_id)
    return list((await db.execute(stmt)).scalars().all())
