"""Add cover_url to events and attended to registrations

Revision ID: 0001_add_cover_attended
Revises: 
Create Date: 2025-02-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_cover_attended'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('events', sa.Column('cover_url', sa.String(length=500), nullable=True))
    op.add_column('registrations', sa.Column('attended', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('registrations', 'attended')
    op.drop_column('events', 'cover_url')
