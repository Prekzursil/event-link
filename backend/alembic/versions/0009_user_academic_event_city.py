"""Add user academic profile fields and event city

Revision ID: 0009_user_academic_event_city
Revises: 0008_add_theme_preference
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_user_academic_event_city"
down_revision = "0008_add_theme_preference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("university", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("faculty", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("study_level", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("study_year", sa.Integer(), nullable=True))

    op.add_column("events", sa.Column("city", sa.String(length=100), nullable=True))
    op.create_index("ix_events_city", "events", ["city"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_events_city", table_name="events")
    op.drop_column("events", "city")

    op.drop_column("users", "study_year")
    op.drop_column("users", "study_level")
    op.drop_column("users", "faculty")
    op.drop_column("users", "university")
    op.drop_column("users", "city")
