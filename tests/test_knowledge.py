def formula_payload():
    return {
        "name": "Base Cream",
        "phases": {
            "phase_a": [{"inci": "Caprylic/Capric Triglyceride", "weight_pct": 8.0}],
            "phase_b": [{"inci": "Aqua", "weight_pct": 83.0}],
            "phase_c": [{"inci": "Glyceryl Stearate", "weight_pct": 3.0}],
            "phase_d": [{"inci": "Panthenol", "weight_pct": 6.0}],
        },
    }


def test_optimize_returns_top3_and_scatter(client, db_session):
    from app.models.ingredient import Ingredient

    for inci, cost, tkdn in [
        ("Caprylic/Capric Triglyceride", 320000, 60),
        ("Aqua", 5000, 100),
        ("Glyceryl Stearate", 260000, 40),
        ("Panthenol", 550000, 0),
    ]:
        db_session.add(
            Ingredient(
                inci=inci, name=inci, smiles="O", default_phase="B",
                default_role="active", cost_per_kg_idr=cost, tkdn_pct=tkdn,
            )
        )
    db_session.commit()
    r = client.post(
        "/api/v1/optimize/pareto?seed=7",
        json={
            "num_trials": 10,
            "locked_ingredients": [{"inci": "Niacinamide", "pct": 2.0}],
            "target_objectives": {"target_viscosity_mpas": 5500.0},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_evaluated"] == 10
    assert len(body["top_candidates"]) == 3
    assert len(body["scatter_3d"]) == 10
    for cand in body["top_candidates"]:
        assert cand["recipe"]["Niacinamide"] == 2.0
        assert abs(sum(cand["recipe"].values()) - 100.0) < 0.05
    got = client.get(f"/api/v1/optimize/pareto/{body['experiment_id']}")
    assert got.status_code == 200
    assert got.json()["experiment_id"] == body["experiment_id"]
    assert client.get("/api/v1/optimize/pareto/exp_nope").status_code == 404


def test_batch_generate_grams(client):
    fid = client.post("/api/v1/formulas", json=formula_payload()).json()["formula_id"]
    r = client.post(
        "/api/v1/batch-sheet/generate",
        json={"formula_id": fid, "batch_size_grams": 500.0, "operator_name": "Rina"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["batch_record_id"].startswith("MBMR-")
    assert body["operator_name"] == "Rina"
    assert len(body["sop_steps"]) == 3
    grams = {i["inci"]: i["grams"] for i in body["scaled_ingredients"]}
    assert grams["Caprylic/Capric Triglyceride"] == 40.0
    assert grams["Aqua"] == 415.0
    assert sum(grams.values()) == 500.0
    assert client.post(
        "/api/v1/batch-sheet/generate",
        json={"formula_id": "form_nope", "batch_size_grams": 500.0},
    ).status_code == 404


def test_similarity_self_match(client):
    fid = client.post("/api/v1/formulas", json=formula_payload()).json()["formula_id"]
    r = client.post(
        "/api/v1/similarity/check",
        json={
            "ingredients": [
                {"inci": "Caprylic/Capric Triglyceride", "weight_pct": 8.0},
                {"inci": "Aqua", "weight_pct": 83.0},
                {"inci": "Glyceryl Stearate", "weight_pct": 3.0},
                {"inci": "Panthenol", "weight_pct": 6.0},
            ]
        },
    )
    assert r.status_code == 200
    top = r.json()["matches"][0]
    assert top["formula_id"] == fid
    assert top["jaccard"] == 1.0
    assert top["cosine"] == 1.0


def test_unconnected_engines_503(client):
    r = client.post(
        "/api/v1/patents/fto-check",
        json={"ingredients": [{"inci": "Aqua", "weight_pct": 100.0}]},
    )
    assert r.status_code == 503
    assert r.json() == {"detail": "patent engine not connected"}
    r = client.post(
        "/api/v1/molecules/conformer-3d",
        json={"smiles": "O", "name": "Aqua"},
    )
    assert r.status_code == 503
    assert r.json() == {"detail": "cheminformatics engine not connected"}


def test_suppliers_empty_list(client):
    r = client.get("/api/v1/suppliers")
    assert r.status_code == 200
    assert r.json() == []
