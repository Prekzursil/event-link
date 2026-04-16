"""Add admin role and user stats columns

Revision ID: 0010_admin_user_mgmt
Revises: 0009_user_academic_event_city
Create Date: 2025-12-18
"""

# Alembic revision variables (revision, down_revision, branch_labels,
# depends_on) are framework-mandated names.
# pylint: disable=invalid-name

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_admin_user_mgmt"
down_revision = "0009_user_academic_event_city"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply admin-role and user-management changes."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # PostgreSQL enum alterations must run outside of a transaction.
        with op.get_context().autocommit_block():
            op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin'"))

    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Revert admin-role and user-management changes."""
    op.drop_column("users", "is_active")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "created_at")

    # Note: PostgreSQL enum values cannot be removed safely.
