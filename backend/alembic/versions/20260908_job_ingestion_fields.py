"""Add ingestion support fields for public job sources.

Revision ID: 20260908_job_ingestion_fields
Revises: 20260903_submission_status_history
"""

from alembic import op
import sqlalchemy as sa


revision = "20260908_job_ingestion_fields"
down_revision = "20260903_submission_status_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(length=1000), nullable=True))
        batch_op.create_index(batch_op.f("ix_jobs_source"), ["source"], unique=False)
        batch_op.create_index(batch_op.f("ix_jobs_source_job_id"), ["source_job_id"], unique=False)
        batch_op.create_unique_constraint("uq_jobs_source_source_job_id", ["source", "source_job_id"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("uq_jobs_source_source_job_id", type_="unique")
        batch_op.drop_index(batch_op.f("ix_jobs_source_job_id"))
        batch_op.drop_index(batch_op.f("ix_jobs_source"))
        batch_op.drop_column("source_url")
