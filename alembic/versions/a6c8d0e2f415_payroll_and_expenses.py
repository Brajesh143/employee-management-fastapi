"""Add salary structures and expense claims.

Revision ID: a6c8d0e2f415
Revises: e4b7c8d9f012
Create Date: 2026-11-01 10:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c8d0e2f415"
down_revision: Union[str, Sequence[str], None] = "e4b7c8d9f012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_structures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("basic_salary", sa.Float(), nullable=False),
        sa.Column("hra", sa.Float(), nullable=False),
        sa.Column("allowance", sa.Float(), nullable=False),
        sa.Column("recurring_deduction", sa.Float(), nullable=False),
        sa.Column("tax_rate", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "effective_from",
            name="uq_salary_structures_employee_effective_from",
        ),
    )
    op.create_index(
        "ix_salary_structures_employee_id",
        "salary_structures",
        ["employee_id"],
    )
    op.create_index(
        "ix_salary_structures_effective_from",
        "salary_structures",
        ["effective_from"],
    )
    op.create_index("ix_salary_structures_id", "salary_structures", ["id"])

    op.create_table(
        "expense_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reimbursement_status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reimbursed_by", sa.Integer(), nullable=True),
        sa.Column("reimbursed_at", sa.DateTime(), nullable=True),
        sa.Column("receipt_name", sa.String(length=255), nullable=True),
        sa.Column("receipt_storage_key", sa.String(length=500), nullable=True),
        sa.Column("receipt_content_type", sa.String(length=100), nullable=True),
        sa.Column("receipt_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reimbursed_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_claims_employee_id", "expense_claims", ["employee_id"])
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"])
    op.create_index("ix_expense_claims_id", "expense_claims", ["id"])


def downgrade() -> None:
    op.drop_index("ix_expense_claims_id", table_name="expense_claims")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_employee_id", table_name="expense_claims")
    op.drop_table("expense_claims")
    op.drop_index("ix_salary_structures_id", table_name="salary_structures")
    op.drop_index(
        "ix_salary_structures_effective_from",
        table_name="salary_structures",
    )
    op.drop_index(
        "ix_salary_structures_employee_id",
        table_name="salary_structures",
    )
    op.drop_table("salary_structures")
