"""Add user-company relationship and controlled role foundation.

Revision ID: a4d93b1a7c2d
Revises: None
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a4d93b1a7c2d"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_company_id"), ["company_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_company_id"))
        batch_op.drop_column("company_id")
