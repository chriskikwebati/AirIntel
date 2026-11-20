"""Add alert_history: one row per device per alert check.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alert_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aqi", sa.Integer(), nullable=False),
        sa.Column("category_name", sa.String(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("dominant_pollutant", sa.String(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_alert_history_device_id", "alert_history", ["device_id"])
    op.create_index("ix_alert_history_checked_at", "alert_history", ["checked_at"])


def downgrade():
    op.drop_table("alert_history")
