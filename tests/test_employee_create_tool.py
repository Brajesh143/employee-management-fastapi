import json
from unittest.mock import Mock

import tools.EmployeeTool as employee_tool_module
import pytest
from models.employee import Employee
from tools.EmployeeTool import EmployeeTool


def _create_arguments(**overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "employee_code": "EMP001",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
    }
    arguments.update(overrides)
    return arguments


def test_employee_tools_register_create_employee() -> None:
    tools = EmployeeTool(Mock(), Mock()).as_tools()

    assert {tool.name for tool in tools} == {
        "get_employees",
        "get_employee",
        "create_employee",
    }


def test_create_employee_tool_does_not_create_before_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_employee = Mock()
    monkeypatch.setattr(employee_tool_module, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        employee_tool_module.employee_crud,
        "create_employee",
        create_employee,
    )
    tool = EmployeeTool(Mock(), Mock(id=1)).create_employee_tool()

    result = json.loads(tool.invoke(_create_arguments()))

    assert result["status"] == "confirmation_required"
    assert result["employee"]["employee_code"] == "EMP001"
    assert "password" not in result["employee"]
    create_employee.assert_not_called()


def test_create_employee_tool_returns_temporary_password_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = Employee(
        employee_code="EMP001",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )
    create_employee = Mock(return_value=employee)
    monkeypatch.setattr(employee_tool_module, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        employee_tool_module,
        "ensure_role_assignment_allowed",
        lambda *_: None,
    )
    monkeypatch.setattr(
        employee_tool_module.employee_crud,
        "create_employee",
        create_employee,
    )
    tool = EmployeeTool(Mock(), Mock(id=1)).create_employee_tool()

    result = json.loads(tool.invoke(_create_arguments(confirmed=True)))

    assert result["status"] == "created"
    assert len(result["temporary_password"]) >= 8
    create_employee.assert_called_once()
