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


def test_create_ok(client):
    r = client.post("/api/v1/formulas", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["formula_id"].startswith("form_")
    assert body["total_weight_pct"] == 100.0
    assert body["status"] == "VALID_BALANCED"
    assert len(body["ingredients"]) == 6
    locked = [i for i in body["ingredients"] if i["is_locked"]]
    assert len(locked) == 1 and locked[0]["inci"] == "Glyceryl Stearate"


def test_create_bad_sum_returns_400(client):
    body = payload()
    body["phases"] = phases(aqua_pct=50.0)
    r = client.post("/api/v1/formulas", json=body)
    assert r.status_code == 400


def test_get_list_update_delete_roundtrip(client):
    created = client.post("/api/v1/formulas", json=payload()).json()
    fid = created["formula_id"]
    assert client.get(f"/api/v1/formulas/{fid}").status_code == 200
    listing = client.get("/api/v1/formulas").json()
    assert any(f["formula_id"] == fid for f in listing)
    updated = payload(name="Moisturizer SPF 30 v2")
    updated["phases"] = phases(aqua_pct=82.0)
    updated["phases"]["phase_d"].append(
        {"inci": "Niacinamide", "name": "Niacinamide", "weight_pct": 1.0}
    )
    r = client.put(f"/api/v1/formulas/{fid}", json=updated)
    assert r.status_code == 200
    assert r.json()["name"] == "Moisturizer SPF 30 v2"
    versions = client.get(f"/api/v1/formulas/{fid}/versions").json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert len(versions[0]["snapshot"]["ingredients"]) == 6
    assert client.delete(f"/api/v1/formulas/{fid}").status_code == 204
    assert client.get(f"/api/v1/formulas/{fid}").status_code == 404


def test_missing_returns_404(client):
    assert client.get("/api/v1/formulas/form_nope").status_code == 404
    assert client.put("/api/v1/formulas/form_nope", json=payload()).status_code == 404
    assert client.delete("/api/v1/formulas/form_nope").status_code == 404
    assert client.get("/api/v1/formulas/form_nope/versions").status_code == 404
