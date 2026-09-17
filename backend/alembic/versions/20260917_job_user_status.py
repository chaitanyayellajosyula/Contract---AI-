"""Add per-user job workflow state.

Revision ID: 20260917_job_user_status
Revises: 20260917_job_source_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_job_user_status"
down_revision = "20260917_job_source_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_user_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_user_status_user_job"),
    )
    op.create_index("ix_job_user_statuses_user_id", "job_user_statuses", ["user_id"], unique=False)
    op.create_index("ix_job_user_statuses_job_id", "job_user_statuses", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_user_statuses_job_id", table_name="job_user_statuses")
    op.drop_index("ix_job_user_statuses_user_id", table_name="job_user_statuses")
    op.drop_table("job_user_statuses")