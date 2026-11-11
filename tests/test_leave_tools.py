import json
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from langchain_core.messages import AIMessage, ToolMessage

import main  # noqa: F401
from database.database import Base
from models.employee import Employee
from models.leave import Leave
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.ai_chat import employee_ai_chat
from schemas.ai_chat import ChatRequest
from tools.leave_tools import create_leave_tools


def _create_employee(db: Session, permission_names: set[str]) -> Employee:
    role = Role(name="Leave Agent Test")
    permissions = [
        Permission(name=name, description=name)
        for name in permission_names
    ]
    db.add_all([role, *permissions])
    db.flush()
    db.add_all(
        RolePermission(role_id=role.id, permission_id=permission.id)
        for permission in permissions
    )
    employee = Employee(
        employee_code="LEAVE001",
        first_name="Lee",
        last_name="Employee",
        email="lee@example.com",
        password_hash="test-hash",
        role_id=role.id,
        leave_balance=12,
    )
    db.add(employee)
    db.commit()
    return employee


def test_leave_agent_reads_self_data_and_prepares_unsubmitted_draft():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        employee = _create_employee(
            db,
            {"leave:read", "leave:create"},
        )
        db.add(
            Leave(
                employee_id=employee.id,
                leave_type="Casual",
                start_date=date(2026, 12, 1),
                end_date=date(2026, 12, 2),
                total_days=2,
                reason="Family event",
                status="Pending",
            )
        )
        db.commit()

        tools = {
            available_tool.name: available_tool
            for available_tool in create_leave_tools(db, employee.id)
        }

        assert tools["get_my_leave_balance"].invoke({}) == {
            "leave_balance_days": 12,
            "unit": "days",
        }
        history = tools["get_my_leave_requests"].invoke({})
        assert history[0]["status"] == "Pending"
        assert history[0]["reason"] == "Family event"

        draft = json.loads(
            tools["prepare_leave_request"].invoke(
                {
                    "leave_type": "Sick",
                    "start_date": "2026-12-10",
                    "end_date": "2026-12-11",
                    "reason": "Recovery",
                }
            )
        )
        assert draft == {
            "leave_type": "Sick",
            "start_date": "2026-12-10",
            "end_date": "2026-12-11",
            "total_days": 2,
            "reason": "Recovery",
        }
        assert db.query(Leave).count() == 1

        invalid = json.loads(
            tools["prepare_leave_request"].invoke(
                {
                    "leave_type": "Vacation",
                    "start_date": "2026-12-10",
                    "end_date": "2026-12-11",
                    "reason": "Trip",
                }
            )
        )
        assert "error" in invalid

    engine.dispose()


def test_leave_agent_only_exposes_actions_granted_by_role():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        employee = _create_employee(db, {"leave:read"})
        tools = {
            available_tool.name
            for available_tool in create_leave_tools(db, employee.id)
        }

    assert tools == {
        "search_leave_policy",
        "get_my_leave_balance",
        "get_my_leave_requests",
    }
    engine.dispose()


def test_policy_search_tool_cites_uploaded_policy_or_reports_no_match(
    monkeypatch,
):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        employee = _create_employee(db, set())
        tool = next(
            candidate
            for candidate in create_leave_tools(db, employee.id)
            if candidate.name == "search_leave_policy"
        )
        monkeypatch.setattr(
            "tools.leave_tools.search_leave_policies",
            lambda _question: [
                {
                    "source": "leave-policy.pdf",
                    "page": 3,
                    "content": "Casual leave allowance is twelve days.",
                }
            ],
        )
        assert "leave-policy.pdf" in tool.invoke(
            {"question": "How much casual leave do I get?"}
        )

        monkeypatch.setattr(
            "tools.leave_tools.search_leave_policies",
            lambda _question: [],
        )
        assert "No matching information" in tool.invoke(
            {"question": "What is the carry-over policy?"}
        )

    engine.dispose()


def test_ai_chat_returns_draft_data_for_explicit_ui_confirmation(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        employee = _create_employee(db, {"leave:read", "leave:create"})

        class FakeAgent:
            def invoke(self, *_args, **_kwargs):
                return {
                    "messages": [
                        ToolMessage(
                            content=json.dumps(
                                {
                                    "response": "Please review the draft.",
                                    "leave_draft": {
                                        "leave_type": "Casual",
                                        "start_date": "2026-12-10",
                                        "end_date": "2026-12-11",
                                        "total_days": 2,
                                        "reason": "Family event",
                                    },
                                }
                            ),
                            name="delegate_to_leave_agent",
                            tool_call_id="tool-call-1",
                        ),
                        AIMessage(
                            content="Please review and confirm the draft."
                        ),
                    ]
                }

        monkeypatch.setattr(
            "routers.ai_chat.create_employee_agent",
            lambda **_kwargs: FakeAgent(),
        )
        response = employee_ai_chat(
            request=ChatRequest(message="Apply for casual leave"),
            db=db,
            current_user=employee,
        )

        assert response.leave_draft is not None
        assert response.leave_draft.leave_type == "Casual"
        assert response.leave_draft.total_days == 2
        assert db.query(Leave).count() == 0

    engine.dispose()
