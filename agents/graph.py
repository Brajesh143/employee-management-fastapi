import json
import logging

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from agents.attendance import create_attendance_agent
from agents.llm import get_llm
from agents.leave import create_leave_agent
from agents.profile import create_profile_agent
from agents.reports import create_reports_agent
from agents.supervisor import create_supervisor_node, route_supervisor
from auth.permissions import has_permission
from models.employee import Employee

logger = logging.getLogger("agent")


def _final_response(agent, question: str) -> tuple[str, dict | None]:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    messages = result.get("messages", [])
    answer = next(
        (
            message.content
            for message in reversed(messages)
            if isinstance(message, AIMessage)
        ),
        "The specialist did not return a response.",
    )
    leave_draft = None
    for message in messages:
        if (
            isinstance(message, ToolMessage)
            and message.name == "prepare_leave_request"
            and isinstance(message.content, str)
        ):
            try:
                draft = json.loads(message.content)
            except json.JSONDecodeError:
                logger.warning("Leave agent returned an invalid draft payload.")
                continue
            if "error" not in draft:
                leave_draft = draft
    if not isinstance(answer, str):
        answer = str(answer)
    return answer, leave_draft


def create_hr_workflow(db: Session, employee_id: int):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise ValueError("Authenticated employee was not found.")

    llm = get_llm()
    profile_agent = create_profile_agent(
        db=db,
        employee_id=employee_id,
        model=llm,
    )
    attendance_agent = create_attendance_agent(
        db=db,
        employee_id=employee_id,
        model=llm,
    )
    leave_agent = create_leave_agent(
        db=db,
        employee_id=employee_id,
        model=llm,
    )
    report_agent = create_reports_agent(
        db=db,
        employee_id=employee_id,
        model=llm,
    )

    delegates = []

    @tool
    def delegate_to_employee_agent(question: str) -> str:
        """Ask the authenticated employee profile specialist a question."""
        answer, _ = _final_response(profile_agent, question)
        return answer

    delegates.append(delegate_to_employee_agent)

    if attendance_agent is not None:

        @tool
        def delegate_to_attendance_agent(question: str) -> str:
            """Ask the scoped attendance specialist a question."""
            answer, _ = _final_response(attendance_agent, question)
            return answer

        delegates.append(delegate_to_attendance_agent)

    @tool
    def delegate_to_leave_agent(question: str) -> str:
        """Ask the leave and leave-policy specialist a question.

        The specialist can prepare, but cannot submit, leave requests.
        """
        answer, leave_draft = _final_response(leave_agent, question)
        return json.dumps(
            {"response": answer, "leave_draft": leave_draft},
            ensure_ascii=False,
        )

    delegates.append(delegate_to_leave_agent)

    if report_agent is not None and has_permission(
        db,
        employee,
        "ai:admin",
    ):

        @tool
        def delegate_to_reports_agent(question: str) -> str:
            """Generate an HR report summary from permission-scoped aggregates."""
            answer, _ = _final_response(report_agent, question)
            return answer

        delegates.append(delegate_to_reports_agent)

    workflow = StateGraph(MessagesState)
    workflow.add_node(
        "supervisor",
        create_supervisor_node(llm.bind_tools(delegates)),
    )
    workflow.add_node("delegates", ToolNode(delegates))
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {"delegates": "delegates", END: END},
    )
    workflow.add_edge("delegates", "supervisor")
    return workflow.compile()
