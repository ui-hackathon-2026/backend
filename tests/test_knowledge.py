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


def test_optimize_returns_top3_and_scatter(authed_client, db_session):
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
    r = authed_client.post(
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
    got = authed_client.get(f"/api/v1/optimize/pareto/{body['experiment_id']}")
    assert got.status_code == 200
    assert got.json()["experiment_id"] == body["experiment_id"]
    assert authed_client.get("/api/v1/optimize/pareto/exp_nope").status_code == 404


def test_batch_generate_grams(authed_client):
    fid = authed_client.post("/api/v1/formulas", json=formula_payload()).json()["formula_id"]
    r = authed_client.post(
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
    assert len(body["shap_contributions"]) == len(body["scaled_ingredients"]) + 1
    assert all(
        set(entry) == {"label", "shap_value"} for entry in body["shap_contributions"]
    )
    assert authed_client.post(
        "/api/v1/batch-sheet/generate",
        json={"formula_id": "form_nope", "batch_size_grams": 500.0},
    ).status_code == 404


def test_shap_additivity():
    from app.ml.predictor import get_lightgbm_predictor
    from app.ml.shap_explainer import explain_stability

    features = {
        "oil_pct": 8.0, "emulsifier_pct": 4.5, "thickener_pct": 0.0,
        "solvent_pct": 83.0, "humectant_pct": 3.5, "active_pct": 1.0,
        "preservative_pct": 0.0, "ingredient_count": 6,
        "temperature_c": 40.0, "duration_days": 90,
        "delta_hlb": 3.5, "sor": 0.562, "unknown_incis": [],
    }
    explained = explain_stability(features)
    predicted = get_lightgbm_predictor().predict(features)["stability_score"]
    assert explained
    assert 0.0 <= predicted <= 1.0


def test_batch_download_pdf(authed_client):
    fid = authed_client.post("/api/v1/formulas", json=formula_payload()).json()["formula_id"]
    record_id = authed_client.post(
        "/api/v1/batch-sheet/generate",
        json={"formula_id": fid, "batch_size_grams": 500.0},
    ).json()["batch_record_id"]
    r = authed_client.get(f"/api/v1/batch-sheet/download/{record_id}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert authed_client.get("/api/v1/batch-sheet/download/MBMR-2099-999").status_code == 404


def test_similarity_self_match(authed_client):
    fid = authed_client.post("/api/v1/formulas", json=formula_payload()).json()["formula_id"]
    r = authed_client.post(
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


def test_unconnected_engines_503(authed_client):
    r = authed_client.post(
        "/api/v1/patents/fto-check",
        json={"ingredients": [{"inci": "Aqua", "weight_pct": 100.0}]},
    )
    assert r.status_code == 503
    assert r.json() == {"detail": "patent engine not connected"}


def test_conformer_niacinamide(authed_client):
    r = authed_client.post(
        "/api/v1/molecules/conformer-3d",
        json={"smiles": "C1=CC(=CN=C1)C(=O)N", "name": "Niacinamide"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["molecule_name"] == "Niacinamide"
    assert body["format"] == "pdb"
    assert "HETATM" in body["pdb_content"]
    assert body["molecular_weight"] == 122.13
    assert body["marker_compound"] is None
    assert len(body["atoms"]) > 0
    first_atom = body["atoms"][0]
    assert set(first_atom) == {"id", "element", "x", "y", "z"}
    assert len(body["bonds"]) > 0
    assert set(body["bonds"][0]) == {"source", "target", "order"}


def test_conformer_green_tea_marker(authed_client):
    r = authed_client.post(
        "/api/v1/molecules/conformer-3d",
        json={"smiles": "C48H78O19", "name": "Green Tea Extract"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["molecule_name"] == "Epigallocatechin Gallate"
    assert body["marker_compound"] == "Epigallocatechin Gallate"
    assert "HETATM" in body["pdb_content"]


def test_conformer_invalid_smiles(authed_client):
    r = authed_client.post(
        "/api/v1/molecules/conformer-3d",
        json={"smiles": "not-a-molecule!!!", "name": "Bogus"},
    )
    assert r.status_code == 422


def test_conformer_unresolved_caveat(authed_client, db_session):
    from app.models.structure import IngredientStructureComponent

    db_session.add(
        IngredientStructureComponent(
            ingredient_inci="Royal Jelly Extract",
            representation_type="unresolved",
            caveat_note="Belum ada struktur terverifikasi untuk ekstrak ini.",
            source="test",
        )
    )
    db_session.commit()
    r = authed_client.post(
        "/api/v1/molecules/conformer-3d",
        json={"name": "Royal Jelly Extract"},
    )
    assert r.status_code == 422
    assert "terverifikasi" in r.json()["detail"]


def test_suppliers_list_and_filter(authed_client, db_session):
    from app.models.catalog import Supplier

    db_session.add(
        Supplier(
            name="PT Aqua Nusa Demo", ingredient_inci="Aqua", grade="Technical",
            halal_certified=True, lead_time_days=7, price_per_kg_idr=5000,
            notes="DEMO DATA",
        )
    )
    db_session.add(
        Supplier(
            name="PT Vita Aktif Demo", ingredient_inci="Niacinamide", grade="USP",
            halal_certified=True, lead_time_days=21, price_per_kg_idr=700000,
            notes="DEMO DATA",
        )
    )
    db_session.commit()
    body = authed_client.get("/api/v1/suppliers").json()
    assert len(body) == 2
    assert body[0]["halal_certified"] is True
    assert "is_synthetic" in body[0]
    assert "city" in body[0]
    filtered = authed_client.get("/api/v1/suppliers?inci=Aqua").json()
    assert len(filtered) == 1
    assert filtered[0]["ingredient_inci"] == "Aqua"


def test_normalize_synonyms():
    from app.services.external_service import normalize_name

    assert normalize_name("Water") == "aqua"
    assert normalize_name("Eau") == "aqua"
    assert normalize_name("Parfum") == "fragrance"


def test_external_novelty(authed_client, db_session):
    from app.models.competitor import CompetitorProduct

    db_session.add(
        CompetitorProduct(
            brand="Wardah", slug="wardah-test-gel", name="Wardah Test Gel",
            url="https://example.test/wardah",
            inci_list=["Aqua", "Niacinamide", "Glycerin", "Phenoxyethanol"],
            ingredient_count=4,
        )
    )
    db_session.add(
        CompetitorProduct(
            brand="Emina", slug="emina-test-lotion", name="Emina Test Lotion",
            url="https://example.test/emina",
            inci_list=["Aqua", "Glycerin", "Niacinamide", "Dimethicone", "Carbomer", "Phenoxyethanol"],
            ingredient_count=6,
        )
    )
    db_session.commit()
    r = authed_client.post(
        "/api/v1/similarity/external",
        json={
            "ingredients": [
                {"inci": "Aqua", "weight_pct": 80.0},
                {"inci": "Niacinamide", "weight_pct": 10.0},
                {"inci": "Glycerin", "weight_pct": 10.0},
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["novelty_score"] <= 1.0
    assert "pseudo-weight" in body["estimated_basis"]
    assert len(body["top_matches"]) == 1
    assert body["top_matches"][0]["brand"] == "Emina"
    assert "aqua" in body["top_matches"][0]["shared_ingredients"]
