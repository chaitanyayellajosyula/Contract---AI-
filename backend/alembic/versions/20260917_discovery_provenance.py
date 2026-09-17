"""Add discovery provider provenance and audit counts.

Revision ID: 20260917_discovery_provenance
Revises: 20260917_source_discovery
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_discovery_provenance"
down_revision = "20260917_source_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.add_column(sa.Column("discovery_provider", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("discovery_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("last_discovered_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("provider_metadata", sa.JSON(), nullable=True))
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(sa.Column("providers_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("failed_provider_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("provider_results", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_column("provider_results")
        batch_op.drop_column("failed_provider_count")
        batch_op.drop_column("duplicate_count")
        batch_op.drop_column("providers_count")
        batch_op.drop_column("duration_ms")
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.drop_column("provider_metadata")
        batch_op.drop_column("last_discovered_at")
        batch_op.drop_column("discovery_key")
        batch_op.drop_column("discovery_provider")