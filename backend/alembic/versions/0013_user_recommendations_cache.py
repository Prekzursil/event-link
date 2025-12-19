"""Add user recommendations cache table

Revision ID: 0013_user_recommendations_cache
Revises: 0012_normalize_event_data
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013_user_recommendations_cache"
down_revision = "0012_normalize_event_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "event_id", name="uq_user_recommendation"),
    )

    op.create_index("ix_user_recommendations_user_id", "user_recommendations", ["user_id"], unique=False)
    op.create_index("ix_user_recommendations_event_id", "user_recommendations", ["event_id"], unique=False)
    op.create_index("ix_user_recommendations_generated_at", "user_recommendations", ["generated_at"], unique=False)
    op.create_index("ix_user_recommendations_user_id_rank", "user_recommendations", ["user_id", "rank"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_recommendations_user_id_rank", table_name="user_recommendations")
    op.drop_index("ix_user_recommendations_generated_at", table_name="user_recommendations")
    op.drop_index("ix_user_recommendations_event_id", table_name="user_recommendations")
    op.drop_index("ix_user_recommendations_user_id", table_name="user_recommendations")
    op.drop_table("user_recommendations")

