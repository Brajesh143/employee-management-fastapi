from langchain.agents import create_agent
from sqlalchemy.orm import Session

from tools.report_tools import create_report_tools

REPORT_AGENT_PROMPT = """
You are the HR reporting specialist. Retrieve report data using the report
tool, then summarize only the returned aggregate values. Ask for a report type
and date range if they are missing. Never disclose employee-level salary data
or invent trends, causes, comparisons, or recommendations unsupported by the
returned data. Report any category marked unavailable without trying to infer
its values.
"""


def create_reports_agent(db: Session, employee_id: int, model):
    """Create the reports specialist when its scoped tools are available."""
    tools = create_report_tools(db=db, employee_id=employee_id)
    if not tools:
        return None
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=REPORT_AGENT_PROMPT,
    )
