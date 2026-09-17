import app.services.orchestration_service as orchestration_service
from app.models.ingredient import Ingredient


class FakeGateway:
    def chat_json(self, messages, model=None, max_tokens=1024):
        text = messages[-1]["content"]
        if "rationale" in text.lower() or "Blueprint" in text:
            return {"rationale": "Emulsi O/W lamellar stabil tropis."}
        return {
            "projectName": "Ultra Hydrating Barrier Gel",
            "brand": "Wardah",
            "category": "Gel-Cream",
            "targetViscosityMpaS": 4800.0,
            "maxCogsIdrPerKg": 45000.0,
            "detectedClaims": ["12H Deep Barrier Hydration"],
            "suggestedHeroIngredients": ["Virgin Coconut Oil (VCO) Riau"],
        }


def seed(db_session):
    for inci, tkdn, origin in [
        ("Aqua", 100.0, None),
        ("Virgin Coconut Oil", 90.0, "Riau"),
        ("Glycerin", 40.0, "Sumatera"),
        ("Niacinamide", 0.0, None),
    ]:
        db_session.add(
            Ingredient(
                inci=inci, name=inci, smiles="O", default_phase="B",
                default_role="active", tkdn_pct=tkdn, origin=origin,
            )
        )
    db_session.commit()


def brief_input():
    return {
        "projectName": "Hydrating Sunscreen Barrier Gel",
        "brand": "Wardah",
        "category": "Gel-Cream",
        "targetSpf": 30,
        "targetViscosityMpaS": 5200,
        "maxCogsIdrPerKg": 42000,
        "targetTkdnPct": 45.0,
        "selectedHeroIngredients": ["Virgin Coconut Oil (VCO) Riau"],
        "specialInstructions": "O/W non-greasy.",
    }


def test_synthesize_blueprint(client, db_session, monkeypatch):
    seed(db_session)
    monkeypatch.setattr(
        orchestration_service, "get_groq_gateway", lambda: FakeGateway()
    )
    r = client.post("/api/v1/orchestrator/synthesize", json=brief_input())
    assert r.status_code == 201
    body = r.json()
    assert body["id"].startswith("bp_")
    assert body["title"].startswith("Hydrating Sunscreen Barrier Gel")
    assert abs(sum(i["weightPct"] for i in body["ingredients"]) - 100.0) < 0.06
    assert {i["phase"] for i in body["ingredients"]} >= {"A", "B", "C", "D"}
    assert body["scientificRationale"] == "Emulsi O/W lamellar stabil tropis."
    assert body["systemHlb"] >= 0


def test_synthesize_validations(client):
    bad_visc = brief_input()
    bad_visc["targetViscosityMpaS"] = 100.0
    assert client.post("/api/v1/orchestrator/synthesize", json=bad_visc).status_code == 400
    bad_cogs = brief_input()
    bad_cogs["maxCogsIdrPerKg"] = 5000.0
    assert client.post("/api/v1/orchestrator/synthesize", json=bad_cogs).status_code == 400


def test_chassis_sum_100(client):
    body = client.get("/api/v1/orchestrator/chassis").json()
    assert len(body) == 4
    brands = {c["brand"] for c in body}
    assert brands == {"Wardah", "Kahf", "Emina", "Labore"}
    for chassis in body:
        total = sum(i["weightPct"] for i in chassis["ingredients"])
        assert abs(total - 100.0) < 0.01, chassis["id"]


def test_hero_ingredients(client, db_session):
    seed(db_session)
    body = client.get("/api/v1/orchestrator/hero-ingredients").json()
    assert len(body) == 3
    assert body[0]["tkdn_pct"] >= body[1]["tkdn_pct"]
    vco = [h for h in body if h["inci"] == "Virgin Coconut Oil"][0]
    assert vco["provenance"] == "Riau"


def test_parse_brief_pdf(client, monkeypatch):
    from tests.test_projects import MINIMAL_PDF, make_pdf

    monkeypatch.setattr(
        orchestration_service, "get_groq_gateway", lambda: FakeGateway()
    )
    pdf = make_pdf(b"Ultra Hydrating Barrier Gel Wardah SPF 30")
    r = client.post(
        "/api/v1/orchestrator/parse-brief-pdf",
        files={"file": ("brief.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extractedBrief"]["brand"] == "Wardah"
    assert body["detectedClaims"] == ["12H Deep Barrier Hydration"]
    assert body["suggestedHeroIngredients"] == ["Virgin Coconut Oil (VCO) Riau"]
    bad = client.post(
        "/api/v1/orchestrator/parse-brief-pdf",
        files={"file": ("notes.txt", b"hi", "text/plain")},
    )
    assert bad.status_code == 422
