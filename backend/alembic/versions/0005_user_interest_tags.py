"""Add user interest tags

Revision ID: 0005_user_interest_tags
Revises: 0004_org_profile_publish_favorites
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_user_interest_tags'
down_revision = '0004_org_profile_publish_favorites'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_interest_tags',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id'), primary_key=True),
    )


def downgrade():
    op.drop_table('user_interest_tags')
