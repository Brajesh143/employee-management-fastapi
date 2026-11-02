import argparse
import getpass
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auth.hashing import Hash
from database import SessionLocal
from models.attendance_correction import AttendanceCorrection
from models.attendence import Attendance
from models.audit_log import AuditLog
from models.candidate import Candidate
from models.designation import Designation  # noqa: F401
from models.employee import Employee
from models.employee_document import EmployeeDocument
from models.expense_claim import ExpenseClaim
from models.interview import Interview
from models.job_opening import JobOpening
from models.leave import Leave
from models.notification import Notification
from models.performance_goal import PerformanceGoal
from models.performance_review import PerformanceReview
from models.permission import Permission  # noqa: F401
from models.role import Role
from models.role_permission import RolePermission
from models.salary import Salary
from models.salary_structure import SalaryStructure
from models.shift import Shift  # noqa: F401
from models.wfh_request import WfhRequest
from seed.permissions import seed_permissions
from seed.role_permissions import seed_role_permissions
from seed.roles import seed_roles
from services.employee_document_storage import get_document_storage

SUPER_ADMIN_EMAIL = "brajesh@gmail.com"
SUPER_ADMIN_CODE = "EMP1001"

EMPLOYEE_DATA_MODELS = (
    Interview,
    Candidate,
    JobOpening,
    AttendanceCorrection,
    Attendance,
    Leave,
    Salary,
    SalaryStructure,
    ExpenseClaim,
    PerformanceGoal,
    PerformanceReview,
    Notification,
    WfhRequest,
    EmployeeDocument,
)


def reset_and_seed_super_admin(db: Session, password: str) -> list[str]:
    """Replace employee and role seed data in one database transaction."""
    if len(password) < 8:
        raise ValueError("Super-admin password must be at least 8 characters.")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Super-admin password must be at most 72 UTF-8 bytes.")

    try:
        with db.begin():
            token_version = (
                db.query(func.max(Employee.token_version)).scalar() or 0
            ) + 1
            document_keys = [
                key
                for (key,) in db.query(EmployeeDocument.storage_key).all()
            ]
            receipt_keys = [
                key
                for (key,) in (
                    db.query(ExpenseClaim.receipt_storage_key)
                    .filter(ExpenseClaim.receipt_storage_key.isnot(None))
                    .all()
                )
            ]

            db.query(AuditLog).update(
                {AuditLog.actor_id: None},
                synchronize_session=False,
            )
            for model in EMPLOYEE_DATA_MODELS:
                db.query(model).delete(synchronize_session=False)

            db.query(Employee).update(
                {Employee.reporting_manager_id: None},
                synchronize_session=False,
            )
            db.query(Employee).delete(synchronize_session=False)
            db.query(RolePermission).delete(synchronize_session=False)
            db.query(Role).delete(synchronize_session=False)
            db.expunge_all()

            seed_permissions(db, commit=False)
            seed_roles(db, commit=False)
            seed_role_permissions(db, commit=False)

            super_admin_role = (
                db.query(Role).filter(Role.name == "Super Admin").one()
            )
            db.add(
                Employee(
                    employee_code=SUPER_ADMIN_CODE,
                    first_name="Super",
                    last_name="Admin",
                    email=SUPER_ADMIN_EMAIL,
                    joining_date=date.today(),
                    role_id=super_admin_role.id,
                    is_active=True,
                    status="Active",
                    token_version=token_version,
                    password_hash=Hash.hash_password(password),
                )
            )
            db.flush()
    except Exception:
        db.rollback()
        raise

    return [*document_keys, *receipt_keys]


def run() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete employee, salary, role, and role-permission data, then "
            "reseed roles and create one super-admin account."
        )
    )
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="required to confirm the destructive database reset",
    )
    args = parser.parse_args()
    if not args.confirm_reset:
        parser.error("pass --confirm-reset to run this destructive reset")

    password = getpass.getpass("New super-admin password: ")
    confirmation = getpass.getpass("Confirm super-admin password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    if len(password) < 8:
        parser.error("super-admin password must be at least 8 characters")
    if len(password.encode("utf-8")) > 72:
        parser.error("super-admin password must be at most 72 UTF-8 bytes")

    db = SessionLocal()
    try:
        storage_keys = reset_and_seed_super_admin(db, password)
        storage = get_document_storage()
        for storage_key in storage_keys:
            storage.delete(storage_key)
    finally:
        db.close()

    print(
        "Reset complete. Seeded one Super Admin account for "
        f"{SUPER_ADMIN_EMAIL}."
    )


if __name__ == "__main__":
    run()
