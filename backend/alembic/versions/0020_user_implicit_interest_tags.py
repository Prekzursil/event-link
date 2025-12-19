"""Add implicit interest tags for online learning

Revision ID: 0020_user_implicit_interest_tags
Revises: 0019_background_jobs_dedupe
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0020_user_implicit_interest_tags"
down_revision = "0019_background_jobs_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_implicit_interest_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "tag_id", name="uq_user_implicit_interest_tag"),
    )

    op.create_index("ix_user_implicit_interest_tags_user_id", "user_implicit_interest_tags", ["user_id"], unique=False)
    op.create_index("ix_user_implicit_interest_tags_tag_id", "user_implicit_interest_tags", ["tag_id"], unique=False)
    op.create_index(
        "ix_user_implicit_interest_tags_last_seen_at",
        "user_implicit_interest_tags",
        ["last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_implicit_interest_tags_last_seen_at", table_name="user_implicit_interest_tags")
    op.drop_index("ix_user_implicit_interest_tags_tag_id", table_name="user_implicit_interest_tags")
    op.drop_index("ix_user_implicit_interest_tags_user_id", table_name="user_implicit_interest_tags")
    op.drop_table("user_implicit_interest_tags")

