"""Co-pilot orchestration over three specialist sub-agents.

Architect parses the request into a FormulationSpec, Auditor and
Sentinel enrich it, Synthesizer streams the natural-language reply.
Every step is emitted as an event so the frontend status tracker
can render progress before tokens arrive.
"""

import json
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.llm import GroqGateway, get_groq_gateway
from app.models.chat import ChatMessage, ChatSession
from app.models.project import Brief
from app.schemas.copilot import ChatRequest, FormulationSpec

ARCHITECT_SYSTEM = (
    "Extract a cosmetic formulation specification from the user message "
    "as JSON with keys: product_category (string), emulsion_type (one of "
    "O/W, W/O, unknown), target_spf (number or null), "
    "viscosity_target_range ([min, max] in mPa.s or null), locked_actives "
    "(array of {name, pct}), stability_requirement (string or null). "
    "Return valid JSON only."
)

AUDITOR_SYSTEM = (
    "Given a formulation spec JSON, assess colloidal thermodynamics as "
    "JSON with keys: delta_hlb_note, sor_note, inversion_risk (one of "
    "low, medium, high), notes. Return valid JSON only."
)

SENTINEL_SYSTEM = (
    "Given locked cosmetic actives, flag regulatory concerns as JSON with "
    "keys: bpom_flags (array of strings), halal_notes (string). Never "
    "invent concentration limits. Return valid JSON only."
)

SYNTHESIZER_SYSTEM = (
    "Jawab sebagai co-pilot formulasi kosmetik dalam Bahasa Indonesia, "
    "ringkas dan praktis, berdasarkan spec JSON dan hasil audit yang "
    "diberikan. Sebutkan angka dan bahan secara spesifik."
)


def new_session_id() -> str:
    return f"sess_{secrets.token_hex(6)}"


def ensure_session(db: Session, body: ChatRequest) -> ChatSession:
    try:
        if body.session_id:
            session = db.get(ChatSession, body.session_id)
            if session is not None:
                return session
        session = ChatSession(
            id=body.session_id or new_session_id(),
            project_id=body.project_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return session


def save_message(db: Session, session_id: str, role: str, content: str) -> None:
    try:
        db.add(ChatMessage(session_id=session_id, role=role, content=content))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc


def load_brief_text(db: Session, brief_id: str | None) -> str:
    if not brief_id:
        return ""
    try:
        brief = db.get(Brief, brief_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if brief is None:
        return ""
    return brief.content_text[:2000]


def run_chat_events(
    db: Session, body: ChatRequest, gateway: GroqGateway | None = None
):
    active = gateway or get_groq_gateway()
    session = ensure_session(db, body)
    yield {"type": "meta", "session_id": session.id}
    save_message(db, session.id, "user", body.message)
    context_parts = [body.message]
    if body.canvas:
        context_parts.append(f"Active canvas: {json.dumps(body.canvas)[:2000]}")
    brief_text = load_brief_text(db, body.brief_id)
    if brief_text:
        context_parts.append(f"Marketing brief: {brief_text}")
    context = "\n".join(context_parts)
    yield {"type": "step", "agent": "architect", "status": "running"}
    spec = FormulationSpec(**active.chat_json(
        [{"role": "user", "content": f"{ARCHITECT_SYSTEM}\n{context}"}],
        model=settings.groq_model_fast,
        max_tokens=1024,
    ))
    yield {"type": "step", "agent": "architect", "status": "done"}
    yield {"type": "step", "agent": "auditor", "status": "running"}
    audit = active.chat_json(
        [{"role": "user", "content": f"{AUDITOR_SYSTEM}\n{spec.model_dump_json()}"}],
        model=settings.groq_model_fast,
        max_tokens=1024,
    )
    yield {"type": "step", "agent": "auditor", "status": "done"}
    yield {"type": "step", "agent": "sentinel", "status": "running"}
    sentinel = active.chat_json(
        [{"role": "user", "content": f"{SENTINEL_SYSTEM}\n{spec.model_dump_json()}"}],
        model=settings.groq_model_fast,
        max_tokens=1024,
    )
    yield {"type": "step", "agent": "sentinel", "status": "done"}
    yield {"type": "step", "agent": "synthesizer", "status": "running"}
    grounding = (
        f"Spec: {spec.model_dump_json()}\n"
        f"Colloid audit: {json.dumps(audit)}\n"
        f"Regulatory notes: {json.dumps(sentinel)}"
    )
    reply_parts: list[str] = []
    for token in active.chat_stream(
        [
            {"role": "system", "content": SYNTHESIZER_SYSTEM},
            {"role": "user", "content": f"{grounding}\nPertanyaan: {body.message}"},
        ],
        model=settings.groq_model_agent,
        max_tokens=1024,
    ):
        reply_parts.append(token)
        yield {"type": "token", "token": token}
    reply = "".join(reply_parts)
    save_message(db, session.id, "assistant", reply)
    yield {
        "type": "result",
        "session_id": session.id,
        "spec": spec.model_dump(),
        "audit": audit,
        "sentinel": sentinel,
        "reply": reply,
    }
