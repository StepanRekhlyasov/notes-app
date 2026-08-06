"""notifications

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notifications_telegram_id", "notifications", ["telegram_id"])


def downgrade():
    op.drop_index("ix_notifications_telegram_id", "notifications")
    op.drop_table("notifications")
