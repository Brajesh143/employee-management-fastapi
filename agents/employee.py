from langchain.agents import create_agent

from agents.llm import get_llm
from agents.prompts import EMPLOYEE_ASSISTANT_PROMPT
from tools.employee_tools import create_employee_tools


def create_employee_agent(
    db,
    employee_id: int,
):
    """
    Create an Employee AI Assistant scoped to one employee.
    """

    llm = get_llm()

    tools = create_employee_tools(
        db=db,
        employee_id=employee_id,
    )

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=EMPLOYEE_ASSISTANT_PROMPT,
    )

    return agent