from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.assistant_agent import (
    AssistantAgentProviderError,
    create_assistant_agent,
    get_assistant_agent_reply,
)
from agents.llm import LLMConfigurationError
from auth.dependencies import get_current_active_user
from database import get_db
from models.employee import Employee
from schemas.chatbot import ChatRequest, ChatResponse

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_active_user),
) -> ChatResponse:
    try:
        agent = create_assistant_agent(db, current_user)
        reply = get_assistant_agent_reply(agent, request.messages)
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AssistantAgentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ChatResponse(reply=reply)
