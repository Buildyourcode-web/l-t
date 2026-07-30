"""Initial schema: violations and camera_status tables.

Revision ID: 001
Revises:
Create Date: 2026-07-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # violations table
    op.create_table(
        "violations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("camera_name", sa.String(length=128), nullable=False),
        sa.Column("track_id", sa.String(length=64), nullable=False),
        sa.Column("violation_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_violations_camera_id", "violations", ["camera_id"])
    op.create_index("ix_violations_detected_at", "violations", ["detected_at"])
    op.create_index("ix_violations_violation_type", "violations", ["violation_type"])
    op.create_index("ix_violations_cam_date", "violations", ["camera_id", "detected_at"])
    op.create_index("ix_violations_type_date", "violations", ["violation_type", "detected_at"])
    op.create_index("ix_violations_date_cam_type", "violations", ["detected_at", "camera_id", "violation_type"])

    # camera_status table
    op.create_table(
        "camera_status",
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("online", sa.Boolean(), nullable=True, default=False),
        sa.Column("last_frame_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True, default=0.0),
        sa.Column("rtsp_url", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("camera_id"),
    )


def downgrade() -> None:
    op.drop_table("camera_status")
    op.drop_index("ix_violations_date_cam_type", table_name="violations")
    op.drop_index("ix_violations_type_date", table_name="violations")
    op.drop_index("ix_violations_cam_date", table_name="violations")
    op.drop_index("ix_violations_violation_type", table_name="violations")
    op.drop_index("ix_violations_detected_at", table_name="violations")
    op.drop_index("ix_violations_camera_id", table_name="violations")
    op.drop_table("violations")
