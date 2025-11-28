"""add indexes for event queries

Revision ID: 0002_add_event_indexes
Revises: 0001_add_cover_attended
Create Date: 2025-11-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_event_indexes'
down_revision = '0001_add_cover_attended'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_events_start_time', 'events', ['start_time'])
    op.create_index('ix_events_category', 'events', ['category'])
    op.create_index('ix_events_owner', 'events', ['owner_id'])


def downgrade():
    op.drop_index('ix_events_owner', table_name='events')
    op.drop_index('ix_events_category', table_name='events')
    op.drop_index('ix_events_start_time', table_name='events')
