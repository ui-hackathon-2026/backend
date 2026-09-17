from app.models.ingredient import Ingredient
from app.services.simulation_service import map_verdict


def ing(name, inci, smiles, pct, phase, role, hlb=None):
    payload = {
        "name": name,
        "inci": inci,
        "smiles": smiles,
        "weight_pct": pct,
        "phase": phase,
        "role": role,
    }
    if hlb is not None:
        payload["hlb"] = hlb
    return payload


BALANCED_FORMULA = {
    "formula_id": "form_99482",
    "formula_name": "SPF 30+ Daily Hydrating Gel-Cream",
    "temperature_c": 40.0,
    "duration_days": 90,
    "engine": "LIGHTGBM_GPU",
    "ingredients": [
        ing("Caprylic Triglyceride", "Caprylic/Capric Triglyceride", "CCCCCCCC(=O)OCC(COC(=O)CCCCCCC)OC(=O)CCCCCCC", 8.0, "A", "emollient"),
        ing("Glyceryl Stearate", "Glyceryl Stearate", "CCCCCCCCCCCCCCCCCC(=O)OCC(CO)O", 3.0, "C", "emulsifier", 3.8),
        ing("Polysorbate 60", "Polysorbate 60", "C64H126O26", 1.5, "C", "emulsifier", 14.9),
        ing("Butylene Glycol", "Butylene Glycol", "CC(CCO)O", 3.5, "B", "humectant"),
        ing("Panthenol", "Panthenol", "CC(C)(CO)C(C(=O)NCCCO)O", 1.0, "D", "active"),
        ing("Aqua Demineralisata", "Aqua", "O", 83.0, "B", "solvent"),
    ],
}


def seed_catalog(db_session):
    for item in BALANCED_FORMULA["ingredients"]:
        db_session.add(
            Ingredient(
                inci=item["inci"],
                name=item["name"],
                smiles=item["smiles"],
                default_phase=item["phase"],
                default_role=item["role"],
            )
        )
    db_session.commit()


def test_simulate_ok_shape(client, db_session):
    seed_catalog(db_session)
    r = client.post("/api/v1/simulate/stability", json=BALANCED_FORMULA)
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"].startswith("run_sim_")
    assert body["formula_id"] == "form_99482"
    assert body["engine_used"] == "STUB_DETERMINISTIC"
    assert body["is_stub"] is True
    assert body["verdict"] in (
        "HIGHLY_STABLE",
        "MODERATELY_STABLE",
        "UNSTABLE_RISK",
        "PHASE_SEPARATION_IMMINENT",
    )
    assert 0.0 <= body["stability_score_40c_90days"] <= 1.0
    assert len(body["droplet_distribution"]) == 5
    assert len(body["rheology_curve"]) == 4
    assert body["thermodynamics"]["sor_ratio"] > 0
    assert isinstance(body["risk_factors"], list)
    assert isinstance(body["stabilizing_factors"], list)
    assert isinstance(body["recommendations"], list)


def test_simulate_bad_weight_sum_returns_400(client, db_session):
    seed_catalog(db_session)
    payload = dict(BALANCED_FORMULA)
    payload["ingredients"] = BALANCED_FORMULA["ingredients"][:4]
    r = client.post("/api/v1/simulate/stability", json=payload)
    assert r.status_code == 400
    assert "100" in r.json()["detail"]


def test_get_run_roundtrip(client, db_session):
    seed_catalog(db_session)
    created = client.post("/api/v1/simulate/stability", json=BALANCED_FORMULA).json()
    r = client.get(f"/api/v1/simulate/stability/{created['run_id']}")
    assert r.status_code == 200
    assert r.json()["run_id"] == created["run_id"]
    assert r.json()["stability_score_40c_90days"] == created["stability_score_40c_90days"]


def test_get_run_missing_returns_404(client):
    r = client.get("/api/v1/simulate/stability/run_sim_missing")
    assert r.status_code == 404
    assert r.json() == {"detail": "Simulation run not found"}


def test_ood_flag_for_unknown_ingredient(client, db_session):
    seed_catalog(db_session)
    body = client.post("/api/v1/simulate/stability", json=BALANCED_FORMULA).json()
    assert body["is_out_of_distribution"] is False
    payload = dict(BALANCED_FORMULA)
    payload["ingredients"] = BALANCED_FORMULA["ingredients"] + [
        ing("Mystery Extract", "Mysteryus Extractus", "CCOCC", 0.5, "D", "active")
    ]
    payload["ingredients"][5] = dict(payload["ingredients"][5], weight_pct=82.5)
    body = client.post("/api/v1/simulate/stability", json=payload).json()
    assert body["is_out_of_distribution"] is True


def test_stub_is_deterministic(client, db_session):
    seed_catalog(db_session)
    first = client.post("/api/v1/simulate/stability", json=BALANCED_FORMULA).json()
    second = client.post("/api/v1/simulate/stability", json=BALANCED_FORMULA).json()
    assert first["run_id"] != second["run_id"]
    assert first["stability_score_40c_90days"] == second["stability_score_40c_90days"]
    assert first["thermodynamics"] == second["thermodynamics"]


def test_verdict_thresholds():
    assert map_verdict(0.95).value == "HIGHLY_STABLE"
    assert map_verdict(0.85).value == "HIGHLY_STABLE"
    assert map_verdict(0.75).value == "MODERATELY_STABLE"
    assert map_verdict(0.60).value == "UNSTABLE_RISK"
    assert map_verdict(0.20).value == "PHASE_SEPARATION_IMMINENT"


def test_smiles_with_whitespace_rejected(client):
    payload = dict(BALANCED_FORMULA)
    payload["ingredients"] = [
        ing("Bad", "Badinci", "CC C", 100.0, "B", "solvent")
    ]
    r = client.post("/api/v1/simulate/stability", json=payload)
    assert r.status_code == 422
