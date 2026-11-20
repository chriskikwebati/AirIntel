"""Create the devices table.

The live database already has this table (it used to be created by create_all on startup),
so this migration only creates it when it is missing.

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("devices"):
        return
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("push_token", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("last_notified_risk_level", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_devices_push_token", "devices", ["push_token"], unique=True)


def downgrade():
    op.drop_table("devices")
