"""Add weighted implicit interests for ML v3 signals

Revision ID: 0021_weighted_implicit_signals
Revises: 0020_user_implicit_interest_tags
Create Date: 2025-12-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0021_weighted_implicit_signals"
down_revision = "0020_user_implicit_interest_tags"
branch_labels = None
depends_on = None


def _create_weighted_interest_table(
    *,
    table_name: str,
    value_column: str,
    unique_name: str,
) -> None:
    """Create a weighted implicit-interest table and its supporting indexes."""
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(value_column, sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", value_column, name=unique_name),
    )
    for suffix, columns in (
        ("user_id", ["user_id"]),
        (value_column, [value_column]),
        ("last_seen_at", ["last_seen_at"]),
    ):
        op.create_index(
            f"ix_{table_name}_{suffix}", table_name, columns, unique=False
        )


def upgrade() -> None:
    """Add weighted implicit-interest tables for the v3 model."""
    op.add_column(
        "user_implicit_interest_tags",
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
    )
    _create_weighted_interest_table(
        table_name="user_implicit_interest_categories",
        value_column="category",
        unique_name="uq_user_implicit_interest_category",
    )
    _create_weighted_interest_table(
        table_name="user_implicit_interest_cities",
        value_column="city",
        unique_name="uq_user_implicit_interest_city",
    )


def downgrade() -> None:
    """Remove the weighted implicit-interest tables added by this migration."""
    op.drop_index(
        "ix_user_implicit_interest_cities_last_seen_at",
        table_name="user_implicit_interest_cities",
    )
    op.drop_index(
        "ix_user_implicit_interest_cities_city",
        table_name="user_implicit_interest_cities",
    )
    op.drop_index(
        "ix_user_implicit_interest_cities_user_id",
        table_name="user_implicit_interest_cities",
    )
    op.drop_table("user_implicit_interest_cities")

    op.drop_index(
        "ix_user_implicit_interest_categories_last_seen_at",
        table_name="user_implicit_interest_categories",
    )
    op.drop_index(
        "ix_user_implicit_interest_categories_category",
        table_name="user_implicit_interest_categories",
    )
    op.drop_index(
        "ix_user_implicit_interest_categories_user_id",
        table_name="user_implicit_interest_categories",
    )
    op.drop_table("user_implicit_interest_categories")

    op.drop_column("user_implicit_interest_tags", "score")
