"""Add language preference to users

Revision ID: 0011_add_language_preference
Revises: 0010_admin_user_mgmt
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_add_language_preference"
down_revision = "0010_admin_user_mgmt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language_preference", sa.String(length=10), nullable=False, server_default="system"),
    )


def downgrade() -> None:
    op.drop_column("users", "language_preference")
