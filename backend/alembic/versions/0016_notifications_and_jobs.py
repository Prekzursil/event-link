"""Add notification preferences and delivery log

Revision ID: 0016_notifications_and_jobs
Revises: 0015_personalization_controls
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_notifications_and_jobs"
down_revision = "0015_personalization_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("email_filling_fast_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_delivery_dedupe_key"),
    )

    op.create_index("ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"], unique=False)
    op.create_index(
        "ix_notification_deliveries_notification_type",
        "notification_deliveries",
        ["notification_type"],
        unique=False,
    )
    op.create_index("ix_notification_deliveries_event_id", "notification_deliveries", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_event_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_notification_type", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_user_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_column("users", "email_filling_fast_enabled")
    op.drop_column("users", "email_digest_enabled")

