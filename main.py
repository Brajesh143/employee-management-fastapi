from fastapi import FastAPI

from database import Base, engine

# Import models explicitly so SQLAlchemy can resolve relationships
from models.department import Department  # noqa: F401
from models.role import Role  # noqa: F401
from models.employee import Employee  # noqa: F401
from routers import department, role, employee, attendence, leave, salary, auth

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Employee Management System API!"}

app.include_router(
    department.router,
    prefix="/departments",
    tags=["Department"]
)

app.include_router(
    role.router,
    prefix="/roles",
    tags=["Role"]
)

app.include_router(
    employee.router,
    prefix="/employees",
    tags=["Employee"]
)

app.include_router(
    attendence.router,
    prefix="/attendences",
    tags=["Attendance"]
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
