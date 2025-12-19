"""Add personalization control tables (hidden tags, blocked organizers)

Revision ID: 0015_personalization_controls
Revises: 0014_event_interactions
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0015_personalization_controls"
down_revision = "0014_event_interactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_hidden_tags",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )
    op.create_index("ix_user_hidden_tags_user_id", "user_hidden_tags", ["user_id"], unique=False)
    op.create_index("ix_user_hidden_tags_tag_id", "user_hidden_tags", ["tag_id"], unique=False)

    op.create_table(
        "user_blocked_organizers",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("organizer_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
    )
    op.create_index("ix_user_blocked_organizers_user_id", "user_blocked_organizers", ["user_id"], unique=False)
    op.create_index(
        "ix_user_blocked_organizers_organizer_id",
        "user_blocked_organizers",
        ["organizer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_blocked_organizers_organizer_id", table_name="user_blocked_organizers")
    op.drop_index("ix_user_blocked_organizers_user_id", table_name="user_blocked_organizers")
    op.drop_table("user_blocked_organizers")

    op.drop_index("ix_user_hidden_tags_tag_id", table_name="user_hidden_tags")
    op.drop_index("ix_user_hidden_tags_user_id", table_name="user_hidden_tags")
    op.drop_table("user_hidden_tags")

