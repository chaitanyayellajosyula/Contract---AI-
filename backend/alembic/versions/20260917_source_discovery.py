"""Add public source discovery records and audit runs.

Revision ID: 20260917_source_discovery
Revises: 20260917_job_user_status
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_source_discovery"
down_revision = "20260917_job_user_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("jobs_endpoint", sa.String(length=1000), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("validation_status", sa.String(length=30), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_discovered_at", sa.DateTime(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("source", "identifier", name="uq_discovered_sources_source_identifier"),
    )
    op.create_index("ix_discovered_sources_source", "discovered_sources", ["source"], unique=False)
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("candidates_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("discovery_runs")
    op.drop_index("ix_discovered_sources_source", table_name="discovered_sources")
    op.drop_table("discovered_sources")