"""Persist trained recommender model weights

Revision ID: 0018_recommender_models
Revises: 0017_event_moderation
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_recommender_models"
down_revision = "0017_event_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommender_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("model_version", name="uq_recommender_models_model_version"),
    )

    op.create_index("ix_recommender_models_model_version", "recommender_models", ["model_version"], unique=False)
    op.create_index("ix_recommender_models_is_active", "recommender_models", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recommender_models_is_active", table_name="recommender_models")
    op.drop_index("ix_recommender_models_model_version", table_name="recommender_models")
    op.drop_table("recommender_models")

