from sqlalchemy.orm import Session

from agents.graph import create_hr_workflow


def create_employee_agent(db: Session, employee_id: int):
    """Create the authenticated employee's LangGraph HR workflow."""
    return create_hr_workflow(db=db, employee_id=employee_id)
