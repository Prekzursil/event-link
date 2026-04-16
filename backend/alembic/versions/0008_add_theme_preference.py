"""Add theme preference to users

Revision ID: 0008_add_theme_preference
Revises: 0007_soft_delete_and_audit
Create Date: 2025-12-18
"""

# Alembic revision variables (revision, down_revision, branch_labels,
# depends_on) are framework-mandated names.
# pylint: disable=invalid-name,no-name-in-module

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_add_theme_preference"
down_revision = "0007_soft_delete_and_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the theme-preference migration."""
    op.add_column(
        "users",
        sa.Column(
            "theme_preference",
            sa.String(length=10),
            nullable=False,
            server_default="system",
        ),
    )


def downgrade() -> None:
    """Revert the theme-preference migration."""
    op.drop_column("users", "theme_preference")
