"""notes.notified

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notes",
        sa.Column("notified", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_notes_notified", "notes", ["notified"])


def downgrade():
    op.drop_index("ix_notes_notified", "notes")
    op.drop_column("notes", "notified")
