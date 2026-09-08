"""Add submission status history.

Revision ID: 20260903_submission_status_history
Revises: 20260903_submission_workflow
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_submission_status_history"
down_revision = "20260903_submission_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_submission_status_history_id", "submission_status_history", ["id"], unique=False)
    op.create_index("ix_submission_status_history_submission_id", "submission_status_history", ["submission_id"], unique=False)
    op.create_index("ix_submission_status_history_changed_by_user_id", "submission_status_history", ["changed_by_user_id"], unique=False)
    op.create_index("ix_submission_status_history_created_at", "submission_status_history", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("submission_status_history")