import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import SessionDep
from app.core.exceptions import LLMUnavailableError
from app.schemas.copilot import ChatRequest
from app.services.copilot_service import run_chat_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat")
def chat(body: ChatRequest, db: SessionDep):
    def event_stream():
        try:
            for event in run_chat_events(db, body):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except LLMUnavailableError as exc:
            logger.error("llm unavailable: %s", exc)
            yield 'data: {"type": "error", "detail": "ai engine unavailable"}\n\n'
        except Exception as exc:
            logger.error("chat failed: %s", exc)
            yield 'data: {"type": "error", "detail": "chat processing failed"}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
