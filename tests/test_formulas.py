from sqlalchemy import text

from app.models.formula import FormulaIngredient
from app.models.ingredient import Ingredient


def phases(aqua_pct=83.0):
    return {
        "phase_a": [
            {
                "inci": "Caprylic/Capric Triglyceride",
                "name": "CCT",
                "weight_pct": 8.0,
            }
        ],
        "phase_b": [
            {"inci": "Aqua", "name": "Aqua", "weight_pct": aqua_pct},
            {
                "inci": "Butylene Glycol",
                "name": "BG",
                "weight_pct": 3.5,
            },
        ],
        "phase_c": [
            {
                "inci": "Glyceryl Stearate",
                "name": "GS",
                "weight_pct": 3.0,
                "is_locked": True,
            },
            {"inci": "Polysorbate 60", "name": "P60", "weight_pct": 1.5},
        ],
        "phase_d": [
            {"inci": "Panthenol", "name": "Panthenol", "weight_pct": 1.0}
        ],
    }


def payload(name="Moisturizer SPF 30", **over):
    body = {
        "name": name,
        "category": "gel-cream_emulsion",
        "batch_size_g": 500.0,
        "notes": "demo",
        "phases": phases(),
    }
    body.update(over)
    return body


def test_create_ok(authed_client):
    r = authed_client.post("/api/v1/formulas", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["formula_id"].startswith("form_")
    assert body["total_weight_pct"] == 100.0
    assert body["status"] == "VALID_BALANCED"
    assert len(body["ingredients"]) == 6
    locked = [i for i in body["ingredients"] if i["is_locked"]]
    assert len(locked) == 1 and locked[0]["inci"] == "Glyceryl Stearate"


def test_cost_snapshot_and_view(authed_client, db_session):
    db_session.add(
        Ingredient(
            inci="Test Oil", name="Test Oil", smiles="CCCC",
            default_phase="A", default_role="emollient",
            cost_per_kg_idr=100000, tkdn_pct=50.0,
        )
    )
    db_session.commit()
    fid = authed_client.post(
        "/api/v1/formulas",
        json={
            "name": "Costed",
            "phases": {
                "phase_a": [{"inci": "Test Oil", "weight_pct": 20.0}],
                "phase_b": [{"inci": "Aqua", "weight_pct": 80.0}],
            },
        },
    ).json()["formula_id"]
    rows = db_session.query(FormulaIngredient).filter_by(formula_id=fid).all()
    by_inci = {r.inci: r for r in rows}
    assert by_inci["Test Oil"].cost_source == "catalog_estimate"
    assert by_inci["Test Oil"].cost_idr_per_kg == 100000
    assert by_inci["Test Oil"].tkdn_pct == 50.0
    db_session.execute(
        text(
            "CREATE VIEW IF NOT EXISTS formulation_cost_view AS "
            "SELECT f.id AS formula_id, f.name AS formula_name, "
            "ROUND(CAST(SUM(fi.weight_pct / 100.0 * COALESCE(fi.cost_idr_per_kg, 0.0)) AS numeric), 0) "
            "AS estimated_cogs_idr_per_kg, "
            "ROUND(CAST(SUM(fi.weight_pct / 100.0 * COALESCE(fi.tkdn_pct, 0.0)) AS numeric), 1) "
            "AS average_tkdn_pct, COUNT(fi.id) AS ingredient_count "
            "FROM formulas f LEFT JOIN formula_ingredients fi ON fi.formula_id = f.id "
            "GROUP BY f.id, f.name"
        )
    )
    view = db_session.execute(
        text(
            "SELECT estimated_cogs_idr_per_kg, average_tkdn_pct "
            "FROM formulation_cost_view WHERE formula_id = :fid"
        ),
        {"fid": fid},
    ).first()
    assert float(view[0]) == 20000.0
    assert float(view[1]) == 10.0


def test_procurement_fields_absent_from_ml_features():
    from app.ml.predictor import LightGBMPredictor

    predictor = LightGBMPredictor()
    sample = predictor.feature_dict(
        {
            "oil_pct": 8.0, "emulsifier_pct": 4.5, "thickener_pct": 0.0,
            "solvent_pct": 83.0, "humectant_pct": 3.5, "active_pct": 1.0,
            "preservative_pct": 0.0, "ingredient_count": 6,
            "temperature_c": 40.0, "duration_days": 90,
            "delta_hlb": 3.5, "sor": 0.562, "unknown_incis": [],
        }
    )
    joined = " ".join(sample.keys()).lower()
    assert "cost" not in joined
    assert "tkdn" not in joined
    assert "price" not in joined


def test_create_bad_sum_returns_400(authed_client):
    body = payload()
    body["phases"] = phases(aqua_pct=50.0)
    r = authed_client.post("/api/v1/formulas", json=body)
    assert r.status_code == 400


def test_get_list_update_delete_roundtrip(authed_client):
    created = authed_client.post("/api/v1/formulas", json=payload()).json()
    fid = created["formula_id"]
    assert authed_client.get(f"/api/v1/formulas/{fid}").status_code == 200
    listing = authed_client.get("/api/v1/formulas").json()
    assert any(f["formula_id"] == fid for f in listing)
    updated = payload(name="Moisturizer SPF 30 v2")
    updated["phases"] = phases(aqua_pct=82.0)
    updated["phases"]["phase_d"].append(
        {"inci": "Niacinamide", "name": "Niacinamide", "weight_pct": 1.0}
    )
    r = authed_client.put(f"/api/v1/formulas/{fid}", json=updated)
    assert r.status_code == 200
    assert r.json()["name"] == "Moisturizer SPF 30 v2"
    versions = authed_client.get(f"/api/v1/formulas/{fid}/versions").json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert len(versions[0]["snapshot"]["ingredients"]) == 6
    assert authed_client.delete(f"/api/v1/formulas/{fid}").status_code == 204
    assert authed_client.get(f"/api/v1/formulas/{fid}").status_code == 404


def test_missing_returns_404(authed_client):
    assert authed_client.get("/api/v1/formulas/form_nope").status_code == 404
    assert authed_client.put("/api/v1/formulas/form_nope", json=payload()).status_code == 404
    assert authed_client.delete("/api/v1/formulas/form_nope").status_code == 404
    assert authed_client.get("/api/v1/formulas/form_nope/versions").status_code == 404


class FakeGateway:
    def chat_json(self, messages, model=None, max_tokens=1024):
        return {
            "title": "Kurangi Glyceryl Stearate",
            "explanation": "Turunkan biaya.",
            "changes": [
                {
                    "ingredient_id": "ing-1",
                    "name": "Glyceryl Stearate",
                    "inci": "Glyceryl Stearate",
                    "new_pct": 2.0,
                    "phase": "C",
                    "action": "modified",
                }
            ],
            "updated_phases": {
                "phase_a": [{"inci": "Caprylic/Capric Triglyceride", "weight_pct": 8.0}],
                "phase_b": [{"inci": "Aqua", "weight_pct": 84.0}],
                "phase_c": [{"inci": "Glyceryl Stearate", "weight_pct": 2.0}],
                "phase_d": [{"inci": "Panthenol", "weight_pct": 6.0}],
            },
        }


def test_propose_adjustment(authed_client, monkeypatch):
    import app.services.formula_service as formula_service

    monkeypatch.setattr(formula_service, "get_groq_gateway", lambda: FakeGateway())
    fid = authed_client.post("/api/v1/formulas", json=payload()).json()["formula_id"]
    r = authed_client.post(
        f"/api/v1/formulas/{fid}/propose-adjustment",
        json={"prompt": "kurangi squalane biar murah"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["formula_id"] == fid
    assert body["changes"][0]["old_pct"] == 3.0
    assert body["changes"][0]["new_pct"] == 2.0
    assert abs(body["total_weight_pct"] - 100.0) < 0.01
    assert authed_client.post(
        "/api/v1/formulas/form_nope/propose-adjustment",
        json={"prompt": "hi"},
    ).status_code == 404


def test_formula_messages_roundtrip(authed_client):
    fid = authed_client.post("/api/v1/formulas", json=payload()).json()["formula_id"]
    assert authed_client.get(f"/api/v1/formulas/{fid}/messages").json() == []
    first = authed_client.post(
        f"/api/v1/formulas/{fid}/messages",
        json={"role": "user", "content": "halo"},
    )
    assert first.status_code == 201
    assert first.json()["session_id"].startswith("sess_")
    second = authed_client.post(
        f"/api/v1/formulas/{fid}/messages",
        json={"role": "assistant", "content": "hai juga"},
    )
    assert second.json()["session_id"] == first.json()["session_id"]
    listing = authed_client.get(f"/api/v1/formulas/{fid}/messages").json()
    assert [m["role"] for m in listing] == ["user", "assistant"]
    assert authed_client.get("/api/v1/formulas/form_nope/messages").status_code == 404
