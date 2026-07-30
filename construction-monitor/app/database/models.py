"""
SQLAlchemy ORM models for the Construction Site AI Monitor.

Tables:
    violations    — every unique violation event
    camera_status — live status of each camera
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Violation(Base):
    """
    Records a single violation event.
    Each row represents ONE unique alert (after deduplication).
    """

    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    camera_name: Mapped[str] = mapped_column(String(128), nullable=False)
    track_id: Mapped[str] = mapped_column(String(64), nullable=False)  # "FIRE" for fire
    violation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Composite indexes for dashboard queries
    __table_args__ = (
        Index("ix_violations_cam_date", "camera_id", "detected_at"),
        Index("ix_violations_type_date", "violation_type", "detected_at"),
        Index("ix_violations_date_cam_type", "detected_at", "camera_id", "violation_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "track_id": self.track_id,
            "violation_type": self.violation_type,
            "confidence": round(self.confidence, 4),
            "image_path": self.image_path,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


class CameraStatus(Base):
    """
    Live status record per camera — upserted on every heartbeat.
    """

    __tablename__ = "camera_status"

    camera_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_frame_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    rtsp_url: Mapped[str] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "online": self.online,
            "last_frame_at": self.last_frame_at.isoformat() if self.last_frame_at else None,
            "fps": round(self.fps, 2),
            "rtsp_url": self.rtsp_url,
        }
