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


def upgrade() -> None:
    op.add_column(
        "user_implicit_interest_tags",
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
    )

    op.create_table(
        "user_implicit_interest_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", name="uq_user_implicit_interest_category"),
    )
    op.create_index(
        "ix_user_implicit_interest_categories_user_id",
        "user_implicit_interest_categories",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_implicit_interest_categories_category",
        "user_implicit_interest_categories",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_user_implicit_interest_categories_last_seen_at",
        "user_implicit_interest_categories",
        ["last_seen_at"],
        unique=False,
    )

    op.create_table(
        "user_implicit_interest_cities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "city", name="uq_user_implicit_interest_city"),
    )
    op.create_index(
        "ix_user_implicit_interest_cities_user_id",
        "user_implicit_interest_cities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_implicit_interest_cities_city",
        "user_implicit_interest_cities",
        ["city"],
        unique=False,
    )
    op.create_index(
        "ix_user_implicit_interest_cities_last_seen_at",
        "user_implicit_interest_cities",
        ["last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_implicit_interest_cities_last_seen_at", table_name="user_implicit_interest_cities")
    op.drop_index("ix_user_implicit_interest_cities_city", table_name="user_implicit_interest_cities")
    op.drop_index("ix_user_implicit_interest_cities_user_id", table_name="user_implicit_interest_cities")
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

