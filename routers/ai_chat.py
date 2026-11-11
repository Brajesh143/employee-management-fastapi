import json
import time
import uuid
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_core.messages import ToolMessage
from sqlalchemy.orm import Session
from agents.callbacks import AgentLoggingCallback
from database import get_db
from auth.permissions import require_permission

from agents.employee import create_employee_agent
from schemas.ai_chat import ChatRequest, ChatResponse, LeaveRequestDraft
from services.leave_policy_rag import (
    MAX_POLICY_FILE_SIZE,
    index_leave_policy,
)


router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)

logger = logging.getLogger("agent")


@router.post("/leave-policies")
def upload_leave_policy(
    file: UploadFile = File(...),
    current_user=Depends(require_permission("ai:admin")),
):
    file_name = file.filename or ""
    content = file.file.read(MAX_POLICY_FILE_SIZE + 1)
    try:
        chunk_count = index_leave_policy(file_name, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "LEAVE_POLICY_INDEX_FAILED | employee_id=%s | file_name=%s",
            current_user.id,
            file_name,
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to index the leave policy document.",
        ) from exc

    logger.info(
        "LEAVE_POLICY_INDEXED | employee_id=%s | file_name=%s | chunks=%s",
        current_user.id,
        file_name,
        chunk_count,
    )
    return {
        "file_name": file_name,
        "chunks_indexed": chunk_count,
    }


@router.post("/chat", response_model=ChatResponse)
def employee_ai_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("ai:chat")),
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
        leave_draft = None
        for message in messages:
            if (
                isinstance(message, ToolMessage)
                and message.name == "delegate_to_leave_agent"
                and isinstance(message.content, str)
            ):
                try:
                    delegation_result = json.loads(message.content)
                except json.JSONDecodeError:
                    logger.warning(
                        "Leave agent returned invalid delegation payload | "
                        "request_id=%s",
                        request_id,
                    )
                    continue
                draft_data = delegation_result.get("leave_draft")
                if draft_data:
                    leave_draft = LeaveRequestDraft.model_validate(draft_data)

        elapsed = time.perf_counter() - start_time

        logger.info(
            "AGENT_REQUEST_COMPLETED | request_id=%s | duration=%.2fs",
            request_id,
            elapsed,
        )

        if not isinstance(answer, str):
            answer = str(answer)

        return ChatResponse(response=answer, leave_draft=leave_draft)

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