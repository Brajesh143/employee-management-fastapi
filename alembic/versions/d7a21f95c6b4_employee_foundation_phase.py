"""Add employee designations, documents, and exit fields.

Revision ID: d7a21f95c6b4
Revises: c4e8f1a92b70
Create Date: 2026-10-31 08:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7a21f95c6b4"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a92b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "designations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_designations_id"), "designations", ["id"], unique=False)
    op.create_index(op.f("ix_designations_name"), "designations", ["name"], unique=True)

    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("designation_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("exit_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("exit_reason", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_employees_designation_id",
            "designations",
            ["designation_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_employees_designation_id"),
            ["designation_id"],
            unique=False,
        )

    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_employee_documents_id"),
        "employee_documents",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_documents_employee_id"),
        "employee_documents",
        ["employee_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_employee_documents_employee_id"), table_name="employee_documents")
    op.drop_index(op.f("ix_employee_documents_id"), table_name="employee_documents")
    op.drop_table("employee_documents")

    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_index(op.f("ix_employees_designation_id"))
        batch_op.drop_constraint("fk_employees_designation_id", type_="foreignkey")
        batch_op.drop_column("exit_reason")
        batch_op.drop_column("exit_date")
        batch_op.drop_column("designation_id")

    op.drop_index(op.f("ix_designations_name"), table_name="designations")
    op.drop_index(op.f("ix_designations_id"), table_name="designations")
    op.drop_table("designations")
