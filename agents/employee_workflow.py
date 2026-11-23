from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agents.employee_edges import route_after_assistant
from agents.employee_nodes import create_assistant_node
from agents.employee_state import EmployeeAgentState


def create_employee_workflow(
    model: BaseChatModel,
    tools: list[BaseTool],
):
    workflow = StateGraph(EmployeeAgentState)
    workflow.add_node("assistant", create_assistant_node(model, tools))
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "assistant")
    workflow.add_conditional_edges(
        "assistant",
        route_after_assistant,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "assistant")
    return workflow.compile()
