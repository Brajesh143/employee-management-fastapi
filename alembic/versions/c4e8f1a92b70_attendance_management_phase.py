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


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _ensure_index(
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    if any(
        index["name"] == index_name
        or (
            index["column_names"] == columns
            and index["unique"] == unique
        )
        for index in indexes
    ):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _ensure_columns_and_foreign_keys(
    table_name: str,
    columns: list[sa.Column],
    foreign_keys: list[tuple[str, str, list[str], list[str]]],
) -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    existing_foreign_keys = inspector.get_foreign_keys(table_name)
    missing_columns = [
        column for column in columns if column.name not in existing_columns
    ]
    missing_foreign_keys = [
        foreign_key
        for foreign_key in foreign_keys
        if not any(
            existing["constrained_columns"] == foreign_key[2]
            and existing["referred_table"] == foreign_key[1]
            and existing["referred_columns"] == foreign_key[3]
            for existing in existing_foreign_keys
        )
    ]

    if not missing_columns and not missing_foreign_keys:
        return

    with op.batch_alter_table(table_name) as batch_op:
        for column in missing_columns:
            batch_op.add_column(column)
        for name, referred_table, local_columns, referred_columns in missing_foreign_keys:
            batch_op.create_foreign_key(
                name,
                referred_table,
                local_columns,
                referred_columns,
            )


def upgrade() -> None:
    if not _has_table("employees") or not _has_table("attendance"):
        raise RuntimeError(
            "The attendance migration requires the existing employees and attendance tables."
        )

    tables = {
        "shifts": (
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
        ),
        "holidays": (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("holiday_date", sa.Date(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("region", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("holiday_date"),
        ),
        "attendance_policies": (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("allow_direct_wfh", sa.Boolean(), nullable=False),
            sa.Column("weekend_days", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("default_shift_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        "audit_logs": (
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
        ),
        "notifications": (
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
        ),
        "wfh_requests": (
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
        ),
        "attendance_corrections": (
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
        ),
    }

    for table_name, elements in tables.items():
        if not _has_table(table_name):
            op.create_table(table_name, *elements)

    _ensure_columns_and_foreign_keys(
        "employees",
        [
            sa.Column("reporting_manager_id", sa.Integer(), nullable=True),
            sa.Column("shift_id", sa.Integer(), nullable=True),
        ],
        [
            (
                "fk_employees_reporting_manager_id",
                "employees",
                ["reporting_manager_id"],
                ["id"],
            ),
            ("fk_employees_shift_id", "shifts", ["shift_id"], ["id"]),
        ],
    )
    _ensure_columns_and_foreign_keys(
        "attendance",
        [
            sa.Column(
                "late_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "early_leave_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "work_mode",
                sa.String(length=20),
                nullable=False,
                server_default="office",
            ),
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="web",
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("shift_id", sa.Integer(), nullable=True),
        ],
        [("fk_attendance_shift_id", "shifts", ["shift_id"], ["id"])],
    )

    for index_name, table_name, columns, unique in (
        ("ix_shifts_id", "shifts", ["id"], False),
        ("ix_holidays_id", "holidays", ["id"], False),
        ("ix_holidays_holiday_date", "holidays", ["holiday_date"], True),
        ("ix_audit_logs_action", "audit_logs", ["action"], False),
        ("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], False),
        ("ix_notifications_employee_id", "notifications", ["employee_id"], False),
        (
            "ix_employees_reporting_manager_id",
            "employees",
            ["reporting_manager_id"],
            False,
        ),
        ("ix_employees_shift_id", "employees", ["shift_id"], False),
        ("ix_attendance_employee_id", "attendance", ["employee_id"], False),
        ("ix_attendance_attendance_date", "attendance", ["attendance_date"], False),
        (
            "uq_attendance_employee_date",
            "attendance",
            ["employee_id", "attendance_date"],
            True,
        ),
        ("ix_wfh_requests_employee_id", "wfh_requests", ["employee_id"], False),
        ("ix_wfh_requests_request_date", "wfh_requests", ["request_date"], False),
        (
            "ix_attendance_corrections_employee_id",
            "attendance_corrections",
            ["employee_id"],
            False,
        ),
    ):
        _ensure_index(index_name, table_name, columns, unique=unique)


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
