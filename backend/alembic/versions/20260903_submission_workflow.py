"""Add company-scoped candidate submissions.

Revision ID: 20260903_submission_workflow
Revises: a4d93b1a7c2d
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_submission_workflow"
down_revision = "a4d93b1a7c2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_jobs_company_id"), ["company_id"], unique=False)
        batch_op.create_foreign_key("fk_jobs_company_id_companies", "companies", ["company_id"], ["id"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="SUBMITTED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_submissions_candidate_job"),
    )
    for column in ("candidate_id", "job_id", "company_id", "submitted_by_user_id"):
        op.create_index(f"ix_submissions_{column}", "submissions", [column], unique=False)


def downgrade() -> None:
    op.drop_table("submissions")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("fk_jobs_company_id_companies", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_jobs_company_id"))
        batch_op.drop_column("company_id")