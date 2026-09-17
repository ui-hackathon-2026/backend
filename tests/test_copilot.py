import json

from app.models.chat import ChatMessage, ChatSession
from app.schemas.copilot import ChatRequest
from app.services.copilot_service import run_chat_events


class FakeGateway:
    def __init__(self):
        self.stream_calls = 0

    def chat_json(self, messages, model=None, max_tokens=1024):
        text = messages[-1]["content"]
        if "Extract a cosmetic" in text:
            return {
                "product_category": "gel-cream_emulsion",
                "emulsion_type": "O/W",
                "target_spf": 30.0,
                "viscosity_target_range": [4000.0, 7000.0],
                "locked_actives": [{"name": "Niacinamide", "pct": 2.0}],
                "stability_requirement": "40C_75RH_90days",
            }
        if "thermodynamics" in text:
            return {
                "delta_hlb_note": "balanced",
                "sor_note": "adequate",
                "inversion_risk": "low",
                "notes": "stable",
            }
        return {"bpom_flags": [], "halal_notes": "vegetable origin"}

    def chat_stream(self, messages, model=None, max_tokens=1024):
        self.stream_calls += 1
        yield "Halo "
        yield "formulator."


def collect(db_session, body):
    return list(run_chat_events(db_session, ChatRequest(**body), FakeGateway()))


def test_chat_creates_session_and_streams_events(authed_client, db_session):
    events = collect(db_session, {"message": "Buatkan moisturizer SPF 30 Niacinamide 2%"})
    kinds = [e["type"] for e in events]
    assert kinds[0] == "meta"
    assert kinds.count("token") == 2
    assert kinds[-1] == "result"
    result = events[-1]
    assert result["spec"]["target_spf"] == 30.0
    assert result["reply"] == "Halo formulator."
    steps = [e["agent"] for e in events if e["type"] == "step"]
    assert steps == [
        "architect", "architect",
        "auditor", "auditor",
        "sentinel", "sentinel",
        "synthesizer",
    ]


def test_chat_reuses_session_and_persists_messages(authed_client, db_session):
    first = collect(db_session, {"message": "halo"})[-1]
    sid = first["session_id"]
    assert sid.startswith("sess_")
    collect(db_session, {"session_id": sid, "message": "lanjut"})
    rows = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_id == sid)
        .order_by(ChatMessage.id)
        .all()
    )
    assert [r.role for r in rows] == ["user", "assistant", "user", "assistant"]
    assert db_session.get(ChatSession, sid) is not None


def test_chat_endpoint_streams_sse(authed_client, db_session, monkeypatch):
    import app.services.copilot_service as copilot_service

    fake = FakeGateway()
    monkeypatch.setattr(copilot_service, "get_groq_gateway", lambda: fake)
    r = authed_client.post(
        "/api/v1/copilot/chat", json={"message": "Buatkan sunscreen ringan"}
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "data: [DONE]" in r.text
    lines = [
        json.loads(line[len("data: "):])
        for line in r.text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    ]
    assert lines[0]["type"] == "meta"
    assert lines[-1]["type"] == "result"
    assert lines[-1]["spec"]["product_category"] == "gel-cream_emulsion"
