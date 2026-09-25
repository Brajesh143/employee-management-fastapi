from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user

from agents.employee import create_employee_agent
from schemas.ai_chat import ChatRequest, ChatResponse


router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)

@router.post("/chat", response_model=ChatResponse)
def employee_ai_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        agent = create_employee_agent(
            db=db,
            employee_id=current_user.id,
        )

        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": request.message,
                    }
                ]
            }
        )

        messages = result.get("messages", [])

        if not messages:
            raise HTTPException(
                status_code=500,
                detail="AI agent returned no response.",
            )

        answer = messages[-1].content

        if not isinstance(answer, str):
            answer = str(answer)

        return ChatResponse(response=answer)

    except HTTPException:
        raise

    except Exception:
        # Log the actual exception in your server logs.
        raise HTTPException(
            status_code=500,
            detail="Unable to process your request. Please try again.",
        )