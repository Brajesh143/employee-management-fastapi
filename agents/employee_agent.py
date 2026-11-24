from httpx import HTTPError
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from ollama import ResponseError
from sqlalchemy.orm import Session

from agents.llm import get_llm
from models.employee import Employee
from schemas.chatbot import ChatMessage
from tools.EmployeeTool import EmployeeTool

SYSTEM_PROMPT = """
You are an Employee Management AI Assistant.

Retrieve accurate employee information using the available tools.
Use the appropriate tool when asked about employee details, department,
designation, or joining date. Never invent employee information. If an
employee is not found, clearly say so.

When asked to create an employee, call the create tool to prepare a preview,
show the complete preview to the user, and ask them to confirm. Do not call
the tool with confirmed=true until the user confirms after seeing the preview.
After creation, provide the generated temporary password only once.
"""


class EmployeeAgentProviderError(Exception):
    pass


def create_employee_agent(db: Session, current_user: Employee):
    return create_agent(
        model=get_llm(),
        tools=EmployeeTool(db, current_user).as_tools(),
        system_prompt=SYSTEM_PROMPT,
    )


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
            "The employee agent failed. Check that Ollama is running, the "
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

    raise EmployeeAgentProviderError("The employee agent returned no text reply.")
