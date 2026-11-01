from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from auth.jwt import JWTHandler

# Import models explicitly so SQLAlchemy can resolve relationships
from models.department import Department  # noqa: F401
from models.designation import Designation  # noqa: F401
from models.employee_document import EmployeeDocument  # noqa: F401
from models.role import Role  # noqa: F401
from models.employee import Employee  # noqa: F401
from routers import (
    department,
    designation,
    role,
    permission,
    employee,
    attendence,
    leave,
    salary,
    auth,
    audit,
    ai_chat,
    reports,
    notifications,
)
from models.shift import Shift  # noqa: F401
from models.holiday import Holiday  # noqa: F401
from models.attendance_policy import AttendancePolicy  # noqa: F401
from models.wfh_request import WfhRequest  # noqa: F401
from models.attendance_correction import AttendanceCorrection  # noqa: F401
from models.audit_log import AuditLog  # noqa: F401
from models.notification import Notification  # noqa: F401
from core.logging_config import setup_logging

load_dotenv()
setup_logging()

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    JWTHandler.validate_configuration()
    yield


app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Employee Management System API!"}

app.include_router(
    department.router,
    prefix="/departments",
    tags=["Department"]
)

app.include_router(
    designation.router,
    prefix="/designations",
    tags=["Designation"]
)

app.include_router(
    role.router,
    prefix="/roles",
    tags=["Role"]
)

app.include_router(
    permission.router,
    prefix="/permissions",
    tags=["Permission Management"],
)

app.include_router(
    employee.router,
    prefix="/employees",
    tags=["Employee"]
)

app.include_router(
    attendence.router,
    prefix="/attendance",
    tags=["Attendance"]
)

app.include_router(
    attendence.router,
    prefix="/attendences",
    tags=["Attendance Legacy"]
)

app.include_router(
    leave.router,
    prefix="/leaves",
    tags=["Leave"]
)

app.include_router(
    salary.router,
    prefix="/salaries",
    tags=["Salary"]
)

app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

app.include_router(
    audit.router,
    prefix="/audit-logs",
    tags=["Audit Logs"]
)

app.include_router(
    ai_chat.router,
    prefix="/api/v1",
)

app.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"]
)

app.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)
