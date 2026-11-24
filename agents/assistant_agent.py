from httpx import HTTPError
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from ollama import ResponseError
from sqlalchemy.orm import Session

from agents.llm import get_llm
from models.employee import Employee
from schemas.chatbot import ChatMessage
from tools.AttendanceTool import AttendanceTool
from tools.EmployeeTool import EmployeeTool

SYSTEM_PROMPT = """
You are an Employee Management Assistant.

Use the employee and attendance tools to answer questions. Never invent
employee or attendance data, and report tool errors clearly.

Check in or check out only when the user explicitly asks you to do so.

When asked to create an employee, prepare a preview, show the complete
details to the user, and ask them to confirm. Do not call the creation tool
with confirmed=true until the user confirms after seeing the preview. After
creation, provide the generated temporary password only once.
"""


class AssistantAgentProviderError(Exception):
    pass


def create_assistant_agent(db: Session, current_user: Employee):
    tools = [
        *EmployeeTool(db, current_user).as_tools(),
        *AttendanceTool(db, current_user).as_tools(),
    ]
    return create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )


def get_assistant_agent_reply(
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
        raise AssistantAgentProviderError(
            "The assistant agent failed. Check that Ollama is running, the "
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

    raise AssistantAgentProviderError("The assistant agent returned no text reply.")
