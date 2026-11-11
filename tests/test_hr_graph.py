from datetime import date

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import main  # noqa: F401
from database.database import Base
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from agents.graph import create_hr_workflow


class FakeSupervisorModel:
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.calls = 0

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": {"question": "Summarize my attendance."},
                        "id": "delegate-call",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="Here is the requested summary.")


class FakeSpecialistAgent:
    def invoke(self, _input):
        return {"messages": [AIMessage(content="One day was present.")]}


def _create_employee(db: Session, permission_names: set[str]) -> Employee:
    role = Role(name="Graph Test Role")
    db.add(role)
    for name in permission_names:
        permission = Permission(name=name, description=name)
        db.add(permission)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    employee = Employee(
        employee_code="GRAPH001",
        first_name="Graph",
        last_name="Employee",
        email="graph@example.com",
        password_hash="test-hash",
        role_id=role.id,
        joining_date=date(2025, 1, 1),
        is_active=True,
    )
    db.add(employee)
    db.commit()
    return employee


def _mock_specialist_agents(monkeypatch):
    for module in ("profile", "attendance", "leave", "reports"):
        monkeypatch.setattr(
            f"agents.{module}.create_agent",
            lambda **_kwargs: FakeSpecialistAgent(),
        )


def test_langgraph_supervisor_delegates_to_attendance_specialist(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, {"attendance:read"})
        supervisor_model = FakeSupervisorModel(
            "delegate_to_attendance_agent"
        )
        monkeypatch.setattr(
            "agents.graph.get_llm",
            lambda: supervisor_model,
        )
        _mock_specialist_agents(monkeypatch)

        workflow = create_hr_workflow(db, employee.id)
        result = workflow.invoke(
            {"messages": [{"role": "user", "content": "My attendance?"}]}
        )

        assert result["messages"][-1].content == (
            "Here is the requested summary."
        )
        assert supervisor_model.calls == 2

    engine.dispose()


def test_langgraph_only_offers_report_delegation_to_authorized_users(
    monkeypatch,
):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(
            db,
            {"ai:admin", "report:read", "attendance:read"},
        )
        supervisor_model = FakeSupervisorModel(
            "delegate_to_reports_agent"
        )
        monkeypatch.setattr(
            "agents.graph.get_llm",
            lambda: supervisor_model,
        )
        _mock_specialist_agents(monkeypatch)

        workflow = create_hr_workflow(db, employee.id)
        result = workflow.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Summarize attendance for March 2026.",
                    }
                ]
            }
        )
        assert result["messages"][-1].content == (
            "Here is the requested summary."
        )

    engine.dispose()
