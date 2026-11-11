from langchain.agents import create_agent
from sqlalchemy.orm import Session

from agents.prompts import EMPLOYEE_ASSISTANT_PROMPT
from tools.employee_tools import create_employee_tools


def create_profile_agent(db: Session, employee_id: int, model):
    """Create the authenticated employee's profile specialist."""
    return create_agent(
        model=model,
        tools=create_employee_tools(db=db, employee_id=employee_id),
        system_prompt=EMPLOYEE_ASSISTANT_PROMPT,
    )
