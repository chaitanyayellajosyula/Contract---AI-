"""Add ingestion run audit records.

Revision ID: 20260917_ingestion_runs
Revises: 20260908_job_ingestion_fields
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_ingestion_runs"
down_revision = "20260908_job_ingestion_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=True),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_source", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")