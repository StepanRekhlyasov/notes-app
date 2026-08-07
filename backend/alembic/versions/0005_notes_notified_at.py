"""notes.notified_at

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notes",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notes_notified_at", "notes", ["notified_at"])
    # Preserve already-sent reminders as "notified now" so they are not resent.
    op.execute(
        """
        UPDATE notes
        SET notified_at = CURRENT_TIMESTAMP
        WHERE notified = 1
        """
    )
    op.drop_index("ix_notes_notified", table_name="notes")
    op.drop_column("notes", "notified")


def downgrade():
    op.add_column(
        "notes",
        sa.Column("notified", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_notes_notified", "notes", ["notified"])
    op.execute(
        """
        UPDATE notes
        SET notified = 1
        WHERE notified_at IS NOT NULL
        """
    )
    op.drop_index("ix_notes_notified_at", table_name="notes")
    op.drop_column("notes", "notified_at")
