from app.models.ingredient import Ingredient


def seed(db_session):
    db_session.add(
        Ingredient(
            inci="Niacinamide", name="Niacinamide (Vitamin B3 USP)",
            smiles="C1=CC(=CN=C1)C(=O)N", default_phase="D",
            default_role="active", cost_per_kg_idr=185000, tkdn_pct=0.0,
            cas_number="98-92-0", description="Brightening active.",
        )
    )
    db_session.add(
        Ingredient(
            inci="Aqua", name="Aqua Demineralisata", smiles="O",
            default_phase="B", default_role="solvent", cost_per_kg_idr=2500,
            tkdn_pct=100.0,
        )
    )
    db_session.add(
        Ingredient(
            inci="Glyceryl Stearate", name="Glyceryl Stearate",
            smiles="CCCC", default_phase="C", default_role="emulsifier",
            hlb=3.8, cost_per_kg_idr=240000, tkdn_pct=35.0,
        )
    )
    db_session.commit()


def moments_payload():
    return {
        "batch_size_g": 1000.0,
        "ingredients": [
            {"name": "Aqua", "inci": "Aqua", "smiles": "O", "weight_pct": 71.5, "phase": "B", "role": "solvent", "cost_per_kg_idr": 2500, "tkdn_pct": 100.0},
            {"name": "GS", "inci": "Glyceryl Stearate", "smiles": "CCCC", "weight_pct": 3.5, "phase": "C", "role": "emulsifier", "hlb": 11.0, "cost_per_kg_idr": 240000, "tkdn_pct": 35.0},
            {"name": "Jojoba", "inci": "Jojoba Oil", "smiles": "CCCC", "weight_pct": 8.0, "phase": "A", "role": "emollient", "hlb": 6.5, "cost_per_kg_idr": 480000, "tkdn_pct": 0.0},
            {"name": "BG", "inci": "Butylene Glycol", "smiles": "CCO", "weight_pct": 17.0, "phase": "B", "role": "humectant", "cost_per_kg_idr": 150000, "tkdn_pct": 0.0},
        ],
    }


def test_ingredients_filters(client, db_session):
    seed(db_session)
    all_items = client.get("/api/v1/workbench/ingredients").json()
    assert all_items["total"] == 3
    assert all_items["items"][0]["id"].startswith("cat-")
    assert "is_halal" in all_items["items"][0]
    phase_d = client.get("/api/v1/workbench/ingredients?phase=D").json()
    assert phase_d["total"] == 1
    assert phase_d["items"][0]["inci"] == "Niacinamide"
    query = client.get("/api/v1/workbench/ingredients?q=niacinamide").json()
    assert query["total"] == 1
    halal = client.get("/api/v1/workbench/ingredients?halal_only=true").json()
    assert halal["total"] == 3
    role = client.get("/api/v1/workbench/ingredients?role=emulsifier").json()
    assert role["total"] == 1


def test_calculate_moments_math(client):
    r = client.post("/api/v1/workbench/calculate-moments", json=moments_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["system_hlb"] == 11.0
    assert body["required_hlb"] == 11.0
    assert body["delta_hlb"] == 0.0
    assert body["sor_ratio"] == 0.4375
    assert body["phase_totals"] == {"A": 8.0, "B": 88.5, "C": 3.5, "D": 0.0}
    assert body["total_weight_pct"] == 100.0
    assert body["estimated_cogs_per_kg_idr"] == 74088.0
    assert body["overall_tkdn_pct"] == 72.7
    assert set(body["radar_metrics"]) == {
        "hlb_equilibrium", "surfactant_efficiency", "viscosity_potential",
        "cost_efficiency", "tkdn_score",
    }
    assert body["warnings"] == []


def test_calculate_moments_warnings_and_400(client):
    bad = moments_payload()
    bad["ingredients"] = [dict(i, weight_pct=10.0) for i in bad["ingredients"]]
    r = client.post("/api/v1/workbench/calculate-moments", json=bad)
    assert r.status_code == 400
    assert r.json() == {"detail": "Total formula concentration must sum to 100% ± 1.0%"}
    no_emulsifier = moments_payload()
    no_emulsifier["ingredients"] = [
        {"name": "Aqua", "inci": "Aqua", "smiles": "O", "weight_pct": 100.0,
         "phase": "B", "role": "solvent"}
    ]
    body = client.post("/api/v1/workbench/calculate-moments", json=no_emulsifier).json()
    assert body["warnings"][0]["code"] == "NO_EMULSIFIER"
    assert body["warnings"][0]["severity"] == "error"


def test_save_draft_roundtrip(client):
    r = client.post(
        "/api/v1/workbench/formulas",
        json={
            "name": "Hydra-Barrier v2", "category": "Gel-Cream",
            "batch_size_g": 1000.0, "notes": "tropical",
            "ingredients": [
                {"name": "Aqua", "inci": "Aqua", "smiles": "O", "weight_pct": 90.0, "phase": "B", "role": "solvent"},
                {"name": "GS", "inci": "Glyceryl Stearate", "smiles": "CCCC", "weight_pct": 10.0, "phase": "C", "role": "emulsifier", "is_locked": True},
            ],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "name", "category", "batch_size_g", "created_at", "updated_at"}
    assert body["name"] == "Hydra-Barrier v2"
    stored = client.get(f"/api/v1/formulas/{body['id']}").json()
    assert stored["total_weight_pct"] == 100.0
    assert len(stored["ingredients"]) == 2


def test_save_draft_bad_sum(client):
    r = client.post(
        "/api/v1/workbench/formulas",
        json={
            "name": "Bad", "batch_size_g": 100.0,
            "ingredients": [
                {"name": "Aqua", "inci": "Aqua", "smiles": "O", "weight_pct": 50.0, "phase": "B", "role": "solvent"}
            ],
        },
    )
    assert r.status_code == 400
    assert r.json() == {"detail": "Total formula concentration must sum to 100% ± 1.0%"}
