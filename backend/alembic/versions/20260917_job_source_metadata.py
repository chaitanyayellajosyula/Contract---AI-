"""Add source-provided job metadata fields.

Revision ID: 20260917_job_source_metadata
Revises: 20260917_ingestion_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_job_source_metadata"
down_revision = "20260917_ingestion_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("apply_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("source_company", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_updated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("source_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("source_metadata")
        batch_op.drop_column("source_updated_at")
        batch_op.drop_column("source_company")
        batch_op.drop_column("apply_url")