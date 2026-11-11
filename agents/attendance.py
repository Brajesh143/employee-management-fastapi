from langchain.agents import create_agent
from sqlalchemy.orm import Session

from tools.attendance_tools import create_attendance_tools

ATTENDANCE_AGENT_PROMPT = """
You are the attendance specialist. Use only the supplied attendance tools to
answer questions about the authenticated employee's records. Never infer that
no record means the employee was absent. Attendance tools are read-only.
"""


def create_attendance_agent(db: Session, employee_id: int, model):
    """Create the attendance specialist when its scoped tools are available."""
    tools = create_attendance_tools(db=db, employee_id=employee_id)
    if not tools:
        return None
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=ATTENDANCE_AGENT_PROMPT,
    )
