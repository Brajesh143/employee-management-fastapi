import json
from datetime import date, datetime
from unittest.mock import Mock

import pytest
import tools.AttendanceTool as attendance_tool_module
from agents import attendance_agent
from models.attendence import Attendance
from tools.AttendanceTool import AttendanceTool


def test_attendance_agent_registers_attendance_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(attendance_agent, "get_llm", lambda: object())

    def fake_create_agent(*, model, tools, system_prompt):
        captured["model"] = model
        captured["tools"] = tools
        captured["system_prompt"] = system_prompt
        return "agent"

    monkeypatch.setattr(attendance_agent, "create_agent", fake_create_agent)
    result = attendance_agent.create_attendance_agent(Mock(), Mock())

    assert result == "agent"
    assert {tool.name for tool in captured["tools"]} == {
        "check_in",
        "check_out",
        "get_today_attendance",
        "get_attendance_history",
    }


def test_check_in_tool_uses_attendance_service_for_signed_in_employee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = Mock(id=7)
    record = Attendance(
        employee_id=7,
        attendance_date=date(2026, 11, 24),
        check_in=datetime(2026, 11, 24, 9),
    )
    check_in = Mock(return_value=record)
    db = Mock()
    monkeypatch.setattr(attendance_tool_module, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        attendance_tool_module.attendance_service,
        "check_in",
        check_in,
    )
    tool = AttendanceTool(db, employee).as_tools()[0]

    result = json.loads(tool.invoke({"work_mode": "office"}))

    assert result["employee_id"] == 7
    check_in.assert_called_once_with(
        db,
        employee,
        work_mode="office",
        source="chatbot",
        notes=None,
    )
