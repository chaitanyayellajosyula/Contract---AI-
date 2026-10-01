"""Add persistent manual outreach drafts and status tracking.

Revision ID: 20261001_outreach_automation
Revises: 20261001_automatic_ingestion_run_marker
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_outreach_automation"
down_revision = "20261001_automatic_ingestion_run_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT', 'READY', 'SENT', 'CANCELLED')", name="ck_outreach_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["vendor_contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    for column in ("company_id", "candidate_id", "job_id", "vendor_id", "contact_id", "created_by_user_id"):
        op.create_index(f"ix_outreach_{column}", "outreach", [column])
    op.create_index("ix_outreach_company_created", "outreach", ["company_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_outreach_company_created", table_name="outreach")
    for column in ("created_by_user_id", "contact_id", "vendor_id", "job_id", "candidate_id", "company_id"):
        op.drop_index(f"ix_outreach_{column}", table_name="outreach")
    op.drop_table("outreach")