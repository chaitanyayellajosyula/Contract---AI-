"""Mark automatic ingestion runs for safe stale-run recovery.

Revision ID: 20261001_automatic_ingestion_run_marker
Revises: 20261001_source_health_cooldown
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_automatic_ingestion_run_marker"
down_revision = "20261001_source_health_cooldown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.add_column(
            sa.Column("is_automatic", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.drop_column("is_automatic")