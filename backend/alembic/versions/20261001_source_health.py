"""Track automatic ingestion health for discovered sources.

Revision ID: 20261001_source_health
Revises: 20260917_discovery_ingestion_counts
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_source_health"
down_revision = "20260917_discovery_ingestion_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.add_column(sa.Column("last_automatic_ingestion_attempt_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_automatic_ingestion_success_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("consecutive_automatic_ingestion_failures", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("last_automatic_ingestion_error", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("discovered_sources") as batch_op:
        batch_op.drop_column("last_automatic_ingestion_error")
        batch_op.drop_column("consecutive_automatic_ingestion_failures")
        batch_op.drop_column("last_automatic_ingestion_success_at")
        batch_op.drop_column("last_automatic_ingestion_attempt_at")