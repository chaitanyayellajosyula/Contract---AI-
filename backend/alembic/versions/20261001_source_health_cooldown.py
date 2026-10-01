"""Add cooldown and per-source automatic-ingestion audit state.

Revision ID: 20261001_source_health_cooldown
Revises: 20261001_source_health
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_source_health_cooldown"
down_revision = "20261001_source_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.add_column(sa.Column("automatic_ingestion_cooldown_started_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.add_column(
            sa.Column("run_type", sa.String(length=40), nullable=False, server_default="source_discovery")
        )
        batch_op.add_column(sa.Column("automatic_ingestion_health_results", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_column("automatic_ingestion_health_results")
        batch_op.drop_column("run_type")
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.drop_column("automatic_ingestion_cooldown_started_at")