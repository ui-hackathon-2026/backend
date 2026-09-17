from app.models.compliance import BpomLimit
from app.models.ingredient import Ingredient


def seed(db_session):
    db_session.add(BpomLimit(inci="Phenoxyethanol", max_pct=1.0, category="preservative"))
    db_session.add(
        Ingredient(
            inci="Phenoxyethanol",
            name="Phenoxyethanol",
            smiles="C1=CC=C(C=C1)OCCO",
            default_phase="D",
            default_role="preservative",
            tkdn_pct=0.0,
        )
    )
    db_session.add(
        Ingredient(
            inci="Virgin Coconut Oil",
            name="Virgin Coconut Oil",
            smiles="CCCC",
            default_phase="A",
            default_role="emollient",
            tkdn_pct=90.0,
        )
    )
    db_session.add(
        Ingredient(
            inci="Aqua",
            name="Aqua",
            smiles="O",
            default_phase="B",
            default_role="solvent",
            tkdn_pct=100.0,
        )
    )
    db_session.commit()


def payload(items):
    return {
        "formula_name": "Test Cream",
        "formula_ingredients": [
            {"inci": inci, "percentage": pct} for inci, pct in items
        ],
    }


def test_compliant_formula(client, db_session):
    seed(db_session)
    r = client.post(
        "/api/v1/compliance/audit",
        json=payload([("Phenoxyethanol", 0.8), ("Aqua", 99.2)]),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["overall_status"] == "COMPLIANT"
    assert body["bpom_audit"] == {"status": "PASSED", "violations": []}
    assert body["halal_audit"]["status"] == "PASSED"
    assert body["halal_audit"]["porcine_risk"] == "ZERO"
    assert body["tkdn_audit"]["score_pct"] == 99.2
    assert body["tkdn_audit"]["meets_threshold"] is True


def test_bpom_violation(client, db_session):
    seed(db_session)
    r = client.post(
        "/api/v1/compliance/audit",
        json=payload([("Phenoxyethanol", 1.2), ("Aqua", 98.8)]),
    )
    body = r.json()
    assert body["overall_status"] == "NON_COMPLIANT"
    assert body["bpom_audit"]["status"] == "FAILED"
    assert body["bpom_audit"]["violations"] == [
        {"inci": "Phenoxyethanol", "percentage": 1.2, "max_allowed_pct": 1.0}
    ]


def test_tkdn_below_threshold(client, db_session):
    seed(db_session)
    r = client.post(
        "/api/v1/compliance/audit",
        json=payload([("Phenoxyethanol", 0.8), ("Aqua", 20.0)]),
    )
    body = r.json()
    assert body["tkdn_audit"]["score_pct"] == 20.0
    assert body["tkdn_audit"]["meets_threshold"] is False
    assert body["tkdn_audit"]["local_components"] == ["Aqua"]


def test_unknown_ingredient_flagged_not_failed(client, db_session):
    seed(db_session)
    r = client.post(
        "/api/v1/compliance/audit",
        json=payload([("Mystery Extract", 2.0), ("Aqua", 98.0)]),
    )
    body = r.json()
    assert body["overall_status"] == "COMPLIANT"
    assert body["halal_audit"]["porcine_risk"] == "UNKNOWN"
    assert body["halal_audit"]["unverified"] == ["Mystery Extract"]
