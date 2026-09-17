from app.models.ingredient import Ingredient


def seed(db_session):
    db_session.add(
        Ingredient(
            inci="Niacinamide", name="Niacinamide (Vitamin B3 USP)",
            smiles="C1=CC(=CN=C1)C(=O)N", default_phase="D",
            default_role="active", cost_per_kg_idr=185000, tkdn_pct=0.0,
        )
    )
    db_session.add(
        Ingredient(
            inci="Virgin Coconut Oil", name="Virgin Coconut Oil",
            smiles="CCCC", default_phase="A", default_role="emollient",
            tkdn_pct=90.0, synonyms=["Cocos Nucifera Oil", "VCO"],
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


def test_search_by_name(client, db_session):
    seed(db_session)
    body = client.get("/api/v1/ingredients/search?q=niacinamide").json()
    assert body["total"] == 1
    assert body["items"][0]["inci"] == "Niacinamide"
    assert body["items"][0]["phase"] == "D"


def test_search_by_synonym(client, db_session):
    seed(db_session)
    body = client.get("/api/v1/ingredients/search?q=vco").json()
    assert body["total"] == 1
    assert body["items"][0]["inci"] == "Virgin Coconut Oil"


def test_search_by_indonesian_function(client, db_session):
    seed(db_session)
    body = client.get("/api/v1/ingredients/search?q=pengemulsi").json()
    assert body["total"] == 1
    assert body["items"][0]["role"] == "emulsifier"
    body = client.get("/api/v1/ingredients/search?q=air").json()
    assert any(i["inci"] == "Aqua" for i in body["items"])


def test_search_filters(client, db_session):
    seed(db_session)
    body = client.get("/api/v1/ingredients/search?q=a&tkdn_min=50").json()
    assert {i["inci"] for i in body["items"]} == {"Virgin Coconut Oil", "Aqua"}
    body = client.get("/api/v1/ingredients/search?q=a&phase=D").json()
    assert [i["inci"] for i in body["items"]] == ["Niacinamide"]
    body = client.get("/api/v1/ingredients/search?q=xyznotfound").json()
    assert body == {"total": 0, "items": []}
