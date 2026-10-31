"""attendance management phase

Revision ID: c4e8f1a92b70
Revises: bbe9465ad3c1
Create Date: 2026-10-31 07:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8f1a92b70"
down_revision: Union[str, Sequence[str], None] = "bbe9465ad3c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("grace_minutes", sa.Integer(), nullable=False),
        sa.Column("unpaid_break_minutes", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_shifts_id"), "shifts", ["id"], unique=False)

    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("holiday_date"),
    )
    op.create_index(op.f("ix_holidays_id"), "holidays", ["id"], unique=False)
    op.create_index(op.f("ix_holidays_holiday_date"), "holidays", ["holiday_date"], unique=True)

    op.create_table(
        "attendance_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("allow_direct_wfh", sa.Boolean(), nullable=False),
        sa.Column("weekend_days", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("default_shift_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("related_type", sa.String(length=50), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_employee_id"), "notifications", ["employee_id"], unique=False)

    op.add_column("employees", sa.Column("reporting_manager_id", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("shift_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_employees_reporting_manager_id"), "employees", ["reporting_manager_id"], unique=False)
    op.create_index(op.f("ix_employees_shift_id"), "employees", ["shift_id"], unique=False)
    op.create_foreign_key(
        "fk_employees_reporting_manager_id",
        "employees",
        "employees",
        ["reporting_manager_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_employees_shift_id",
        "employees",
        "shifts",
        ["shift_id"],
        ["id"],
    )

    op.add_column("attendance", sa.Column("late_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("attendance", sa.Column("early_leave_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("attendance", sa.Column("work_mode", sa.String(length=20), nullable=False, server_default="office"))
    op.add_column("attendance", sa.Column("source", sa.String(length=20), nullable=False, server_default="web"))
    op.add_column("attendance", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("attendance", sa.Column("shift_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_attendance_shift_id", "attendance", "shifts", ["shift_id"], ["id"])
    op.create_index("ix_attendance_employee_id", "attendance", ["employee_id"], unique=False)
    op.create_index("ix_attendance_attendance_date", "attendance", ["attendance_date"], unique=False)
    op.create_index("uq_attendance_employee_date", "attendance", ["employee_id", "attendance_date"], unique=True)

    op.create_table(
        "wfh_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wfh_requests_employee_id"), "wfh_requests", ["employee_id"], unique=False)
    op.create_index(op.f("ix_wfh_requests_request_date"), "wfh_requests", ["request_date"], unique=False)

    op.create_table(
        "attendance_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("original_attendance_id", sa.Integer(), nullable=False),
        sa.Column("requested_check_in", sa.DateTime(), nullable=True),
        sa.Column("requested_check_out", sa.DateTime(), nullable=True),
        sa.Column("requested_work_mode", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["original_attendance_id"], ["attendance.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_attendance_corrections_employee_id"),
        "attendance_corrections",
        ["employee_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("attendance_corrections")
    op.drop_table("wfh_requests")
    op.drop_index("uq_attendance_employee_date", table_name="attendance")
    op.drop_constraint("fk_attendance_shift_id", "attendance", type_="foreignkey")
    op.drop_column("attendance", "shift_id")
    op.drop_column("attendance", "notes")
    op.drop_column("attendance", "source")
    op.drop_column("attendance", "work_mode")
    op.drop_column("attendance", "early_leave_minutes")
    op.drop_column("attendance", "late_minutes")
    op.drop_constraint("fk_employees_shift_id", "employees", type_="foreignkey")
    op.drop_constraint("fk_employees_reporting_manager_id", "employees", type_="foreignkey")
    op.drop_column("employees", "shift_id")
    op.drop_column("employees", "reporting_manager_id")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("attendance_policies")
    op.drop_table("holidays")
    op.drop_table("shifts")
