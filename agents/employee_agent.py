from collections.abc import Sequence

from httpx import HTTPError
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from ollama import ResponseError
from sqlalchemy.orm import Session

from agents.employee_workflow import create_employee_workflow
from agents.llm import get_llm
from models.employee import Employee
from schemas.chatbot import ChatMessage
from tools.EmployeeTool import EmployeeTool


class EmployeeAgentProviderError(Exception):
    pass


def create_employee_agent(db: Session, current_user: Employee):
    model = get_llm()
    tools: Sequence[BaseTool] = EmployeeTool(db, current_user).as_tools()
    return create_employee_workflow(model, list(tools))


def get_employee_agent_reply(
    agent,
    messages: list[ChatMessage],
) -> str:
    conversation = [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in messages
    ]
    try:
        result = agent.invoke(
            {"messages": conversation},
            config={"recursion_limit": 12},
        )
    except (HTTPError, ResponseError, GraphRecursionError) as exc:
        raise EmployeeAgentProviderError(
            "The employee workflow failed. Check that Ollama is running, the "
            "model is available, and the model supports tool calls."
        ) from exc

    for message in reversed(result.get("messages", [])):
        if (
            isinstance(message, AIMessage)
            and not message.tool_calls
            and isinstance(message.content, str)
            and message.content.strip()
        ):
            return message.content.strip()

    raise EmployeeAgentProviderError(
        "The employee agent returned no text reply."
    )
