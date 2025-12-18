"""Add soft-delete columns and audit logs

Revision ID: 0007_soft_delete_and_audit
Revises: 0006_background_jobs
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_soft_delete_and_audit"
down_revision = "0006_background_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "events",
        sa.Column("deleted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_events_deleted_at", "events", ["deleted_at"], unique=False)

    op.add_column("registrations", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "registrations",
        sa.Column("deleted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_registrations_deleted_at", "registrations", ["deleted_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_registrations_deleted_at", table_name="registrations")
    op.drop_column("registrations", "deleted_by_user_id")
    op.drop_column("registrations", "deleted_at")

    op.drop_index("ix_events_deleted_at", table_name="events")
    op.drop_column("events", "deleted_by_user_id")
    op.drop_column("events", "deleted_at")

