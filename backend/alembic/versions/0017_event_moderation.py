"""Add event moderation fields for trust & safety

Revision ID: 0017_event_moderation
Revises: 0016_notifications_and_jobs
Create Date: 2025-12-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_event_moderation"
down_revision = "0016_notifications_and_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("moderation_score", sa.Float(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("events", sa.Column("moderation_flags", sa.JSON(), nullable=True))
    op.add_column(
        "events",
        sa.Column("moderation_status", sa.String(length=20), nullable=False, server_default="clean"),
    )
    op.add_column("events", sa.Column("moderation_reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "events",
        sa.Column("moderation_reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_index("ix_events_moderation_status", "events", ["moderation_status"], unique=False)
    op.create_index("ix_events_moderation_score", "events", ["moderation_score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_events_moderation_score", table_name="events")
    op.drop_index("ix_events_moderation_status", table_name="events")

    op.drop_column("events", "moderation_reviewed_by_user_id")
    op.drop_column("events", "moderation_reviewed_at")
    op.drop_column("events", "moderation_status")
    op.drop_column("events", "moderation_flags")
    op.drop_column("events", "moderation_score")

