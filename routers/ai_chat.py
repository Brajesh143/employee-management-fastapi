import time
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from agents.callbacks import AgentLoggingCallback
from database import get_db
from auth.dependencies import get_current_user

from agents.employee import create_employee_agent
from schemas.ai_chat import ChatRequest, ChatResponse


router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)

logger = logging.getLogger("agent")

@router.post("/chat", response_model=ChatResponse)
def employee_ai_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    logger.info(
        "AGENT_REQUEST_STARTED | request_id=%s | employee_id=%s",
        request_id,
        current_user.id,
    )

    try:
        agent = create_employee_agent(
            db=db,
            employee_id=current_user.id,
        )

        callback = AgentLoggingCallback()

        logger.info(
            "AGENT_INVOCATION_STARTED | request_id=%s",
            request_id,
        )

        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": request.message,
                    }
                ]
            },
            config={
                "callbacks": [callback],
                "recursion_limit": 10,
                "metadata": {
                    "request_id": request_id,
                },
            },
        )

        messages = result.get("messages", [])

        if not messages:
            raise HTTPException(
                status_code=500,
                detail="AI agent returned no response.",
            )

        answer = messages[-1].content

        elapsed = time.perf_counter() - start_time

        logger.info(
            "AGENT_REQUEST_COMPLETED | request_id=%s | duration=%.2fs",
            request_id,
            elapsed,
        )

        if not isinstance(answer, str):
            answer = str(answer)

        return ChatResponse(response=answer)

    except Exception:
        elapsed = time.perf_counter() - start_time

        logger.exception(
            "AGENT_REQUEST_FAILED | request_id=%s | duration=%.2fs",
            request_id,
            elapsed,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed. Reference: {request_id}",
        )