from typing import Literal

from langchain_core.messages import AIMessage

from agents.employee_state import EmployeeAgentState


def route_after_assistant(
    state: EmployeeAgentState,
) -> Literal["tools", "end"]:
    messages = state["messages"]
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "tools"
    return "end"
