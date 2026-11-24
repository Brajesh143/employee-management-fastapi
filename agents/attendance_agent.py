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

SYSTEM_PROMPT = """
You are an Attendance Assistant for the signed-in employee.

Use the attendance tools to report today's attendance or attendance history.
Never invent attendance data. Check in or check out only when the user
explicitly asks you to do so. Report tool errors clearly, including when a
WFH check-in is not allowed.
"""


class AttendanceAgentProviderError(Exception):
    pass


def create_attendance_agent(db: Session, current_user: Employee):
    return create_agent(
        model=get_llm(),
        tools=AttendanceTool(db, current_user).as_tools(),
        system_prompt=SYSTEM_PROMPT,
    )


def get_attendance_agent_reply(
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
        raise AttendanceAgentProviderError(
            "The attendance agent failed. Check that Ollama is running, the "
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

    raise AttendanceAgentProviderError(
        "The attendance agent returned no text reply."
    )
