"""Add leave approval workflow and cancellation history.

Revision ID: e4b7c8d9f012
Revises: f1c2a3b4d5e6
Create Date: 2026-11-01 10:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b7c8d9f012"
down_revision: Union[str, Sequence[str], None] = "f1c2a3b4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leaves") as batch_op:
        batch_op.add_column(
            sa.Column(
                "approval_stage",
                sa.String(length=20),
                nullable=False,
                server_default="hr",
            )
        )
        batch_op.add_column(
            sa.Column("manager_approved_by", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_leaves_manager_approved_by_employees",
            "employees",
            ["manager_approved_by"],
            ["id"],
        )
        batch_op.add_column(
            sa.Column("manager_approved_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("hr_approved_by", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_leaves_hr_approved_by_employees",
            "employees",
            ["hr_approved_by"],
            ["id"],
        )
        batch_op.add_column(
            sa.Column("hr_approved_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("rejected_by", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_leaves_rejected_by_employees",
            "employees",
            ["rejected_by"],
            ["id"],
        )
        batch_op.add_column(
            sa.Column("rejected_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cancelled_by", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_leaves_cancelled_by_employees",
            "employees",
            ["cancelled_by"],
            ["id"],
        )
        batch_op.add_column(
            sa.Column("cancelled_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cancellation_reason", sa.Text(), nullable=True)
        )
    op.create_index("ix_leaves_employee_id", "leaves", ["employee_id"])
    op.create_index("ix_leaves_status", "leaves", ["status"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE leaves SET approval_stage = 'completed' "
            "WHERE status = 'Approved'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE leaves SET approval_stage = 'rejected' "
            "WHERE status = 'Rejected'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE leaves SET approval_stage = 'manager' "
            "WHERE status = 'Pending' AND employee_id IN "
            "(SELECT id FROM employees WHERE reporting_manager_id IS NOT NULL)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_leaves_status", table_name="leaves")
    op.drop_index("ix_leaves_employee_id", table_name="leaves")
    with op.batch_alter_table("leaves") as batch_op:
        batch_op.drop_constraint(
            "fk_leaves_cancelled_by_employees",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_leaves_rejected_by_employees",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_leaves_hr_approved_by_employees",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_leaves_manager_approved_by_employees",
            type_="foreignkey",
        )
        batch_op.drop_column("cancellation_reason")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("cancelled_by")
        batch_op.drop_column("rejected_at")
        batch_op.drop_column("rejected_by")
        batch_op.drop_column("hr_approved_at")
        batch_op.drop_column("hr_approved_by")
        batch_op.drop_column("manager_approved_at")
        batch_op.drop_column("manager_approved_by")
        batch_op.drop_column("approval_stage")
