import json
from datetime import date

from models.employee import Employee
from tools.EmployeeTool import _employee_summary


def test_employee_summary_includes_employee_fields_except_password_hash() -> None:
    employee = Employee(
        employee_code="EMP001",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        salary=125000,
        joining_date=date(2020, 1, 1),
        password_hash="must-not-be-returned",
    )

    summary = _employee_summary(employee)
    serialized_summary = json.dumps(summary, default=str)

    assert set(Employee.__table__.columns.keys()) - {"password_hash"} <= summary.keys()
    assert summary["salary"] == 125000
    assert summary["joining_date"] == date(2020, 1, 1)
    assert "password_hash" not in summary
    assert "must-not-be-returned" not in serialized_summary
