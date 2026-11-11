from langchain.agents import create_agent
from sqlalchemy.orm import Session

from tools.leave_tools import create_leave_tools

LEAVE_AGENT_PROMPT = """
You are the leave specialist. Use the supplied tools for employee leave data
and policy documents. Ground policy statements only in retrieved HR documents,
cite source filenames, and direct the employee to HR when the policy is not
covered. Leave request tools only prepare drafts; never claim submission,
approval, or rejection.
"""


def create_leave_agent(db: Session, employee_id: int, model):
    """Create the leave and leave-policy specialist."""
    return create_agent(
        model=model,
        tools=create_leave_tools(db=db, employee_id=employee_id),
        system_prompt=LEAVE_AGENT_PROMPT,
    )
