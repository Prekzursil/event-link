"""add organizer profile fields, event status/publish_at, favorites

Revision ID: 0004_org_profile_publish_favorites
Revises: 0003_add_password_reset_tokens
Create Date: 2025-02-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_org_profile_publish_favorites"
down_revision = "0003_add_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("org_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("org_description", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("org_logo_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("org_website", sa.String(length=255), nullable=True))

    op.add_column("events", sa.Column("status", sa.String(length=20), nullable=False, server_default="published"))
    op.add_column("events", sa.Column("publish_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.alter_column("events", "status", server_default=None)

    op.create_table(
        "favorite_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "event_id", name="uq_favorite_event"),
    )


def downgrade() -> None:
    op.drop_table("favorite_events")
    op.drop_column("events", "publish_at")
    op.drop_column("events", "status")
    op.drop_column("users", "org_website")
    op.drop_column("users", "org_logo_url")
    op.drop_column("users", "org_description")
    op.drop_column("users", "org_name")
