"""Add BackgroundJob dedupe_key for DB-level job deduplication

Revision ID: 0019_background_jobs_dedupe
Revises: 0018_recommender_models
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0019_background_jobs_dedupe"
down_revision = "0018_recommender_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("background_jobs", sa.Column("dedupe_key", sa.String(length=200), nullable=True))
    op.create_index("ix_background_jobs_dedupe_key", "background_jobs", ["dedupe_key"], unique=False)
    op.create_unique_constraint(
        "uq_background_job_dedupe_key",
        "background_jobs",
        ["job_type", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_background_job_dedupe_key", "background_jobs", type_="unique")
    op.drop_index("ix_background_jobs_dedupe_key", table_name="background_jobs")
    op.drop_column("background_jobs", "dedupe_key")

