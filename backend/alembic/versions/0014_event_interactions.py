"""Add event interactions tracking table

Revision ID: 0014_event_interactions
Revises: 0013_user_recommendations_cache
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_event_interactions"
down_revision = "0013_user_recommendations_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
    )

    op.create_index("ix_event_interactions_user_id", "event_interactions", ["user_id"], unique=False)
    op.create_index("ix_event_interactions_event_id", "event_interactions", ["event_id"], unique=False)
    op.create_index("ix_event_interactions_interaction_type", "event_interactions", ["interaction_type"], unique=False)
    op.create_index("ix_event_interactions_occurred_at", "event_interactions", ["occurred_at"], unique=False)
    op.create_index(
        "ix_event_interactions_user_id_occurred_at",
        "event_interactions",
        ["user_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_event_interactions_user_id_occurred_at", table_name="event_interactions")
    op.drop_index("ix_event_interactions_occurred_at", table_name="event_interactions")
    op.drop_index("ix_event_interactions_interaction_type", table_name="event_interactions")
    op.drop_index("ix_event_interactions_event_id", table_name="event_interactions")
    op.drop_index("ix_event_interactions_user_id", table_name="event_interactions")
    op.drop_table("event_interactions")

