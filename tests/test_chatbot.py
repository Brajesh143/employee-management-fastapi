from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from agents import employee_agent
from agents.employee_edges import route_after_assistant
from auth.dependencies import get_current_active_user
from routers import chatbot
from schemas.chatbot import ChatMessage, ChatRequest


def test_chat_request_requires_a_user_message_last() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(messages=[ChatMessage(role="assistant", content="Hello")])


def test_employee_agent_registers_employee_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(employee_agent, "get_llm", lambda: object())

    def fake_create_workflow(model, tools):
        captured["model"] = model
        captured["tools"] = tools
        return "workflow"

    monkeypatch.setattr(
        employee_agent,
        "create_employee_workflow",
        fake_create_workflow,
    )

    result = employee_agent.create_employee_agent(Mock(), Mock())

    assert result == "workflow"
    assert {tool.name for tool in captured["tools"]} == {
        "get_employees",
        "get_employee",
    }
    assert captured["model"] is not None


def test_employee_agent_returns_final_assistant_message() -> None:
    class FakeAgent:
        def invoke(self, _: dict, config: dict) -> dict:
            assert config == {"recursion_limit": 12}
            return {
                "messages": [
                    AIMessage(content="Intermediate", tool_calls=[{
                        "name": "get_employees",
                        "args": {},
                        "id": "tool-call-1",
                    }]),
                    AIMessage(content=" Employee found. "),
                ]
            }

    reply = employee_agent.get_employee_agent_reply(
        FakeAgent(),
        [ChatMessage(role="user", content="Find an employee")],
    )

    assert reply == "Employee found."


def test_employee_agent_routes_tool_calls_to_tools_node() -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_employee",
                "args": {"employee_code": "EMP001"},
                "id": "tool-call-1",
            }
        ],
    )
    final_answer = AIMessage(content="Employee found.")

    assert route_after_assistant({"messages": [tool_call]}) == "tools"
    assert route_after_assistant({"messages": [final_answer]}) == "end"


def test_chat_endpoint_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(chatbot.router)

    response = TestClient(app).post(
        "/chatbot/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 401


def test_authenticated_chat_endpoint_returns_agent_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(chatbot.router)
    app.dependency_overrides[get_current_active_user] = lambda: object()
    app.dependency_overrides[chatbot.get_db] = lambda: object()
    monkeypatch.setattr(chatbot, "create_employee_agent", lambda *_: object())
    monkeypatch.setattr(
        chatbot,
        "get_employee_agent_reply",
        lambda *_: "Hello!",
    )

    response = TestClient(app).post(
        "/chatbot/chat",
        headers={"Authorization": "Bearer test-token"},
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello!"}


