"""Add automatic ingestion counts to discovery runs.

Revision ID: 20260917_discovery_ingestion_counts
Revises: 20260917_discovery_provenance
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_discovery_ingestion_counts"
down_revision = "20260917_discovery_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_column("failed_count")
        batch_op.drop_column("succeeded_count")
        batch_op.drop_column("selected_count")