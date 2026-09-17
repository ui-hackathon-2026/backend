import app.services.compliance_service as compliance_service
from app.models.compliance import BpomLimit
from app.models.ingredient import Ingredient
from app.models.knowledge import KnowledgeChunk


class FakeGateway:
    def chat_json(self, messages, model=None, max_tokens=1024):
        text = messages[-1]["content"]
        if "Temuan audit" in text:
            return {
                "toxicology_evaluation": "Aman dalam batas.",
                "mandatory_label_warnings": ["Simpan di tempat sejuk."],
                "local_substitution_recommendations": [],
            }
        return {"answer": "Alpha-Arbutin aman hingga 2%.", "confidence": 0.9}


def seed(db_session):
    db_session.add(BpomLimit(inci="Phenoxyethanol", max_pct=1.0, category="preservative"))
    db_session.add(
        Ingredient(
            inci="Phenoxyethanol", name="Phenoxyethanol", smiles="C",
            default_phase="D", default_role="preservative", tkdn_pct=0.0,
        )
    )
    db_session.add(
        Ingredient(
            inci="Virgin Coconut Oil", name="Virgin Coconut Oil", smiles="CCCC",
            default_phase="A", default_role="emollient", tkdn_pct=90.0,
            synonyms=["Cocos Nucifera Oil", "VCO"],
        )
    )
    db_session.add(
        Ingredient(
            inci="Aqua", name="Aqua", smiles="O", default_phase="B",
            default_role="solvent", tkdn_pct=100.0,
        )
    )
    db_session.add(
        KnowledgeChunk(
            id="bpom_test_phenoxy", title="Phenoxyethanol",
            regulation="Peraturan BPOM No. 17 Tahun 2022",
            appendix="Lampiran V", clause_entry="Entri No. 29",
            category="preservative", substance_name="Phenoxyethanol",
            inci_name="Phenoxyethanol", synonyms=["2-Phenoxyethanol"],
            cas_number="122-99-6", max_concentration_pct=1.0,
            raw_text="Phenoxyethanol maksimum 1,0%.",
        )
    )
    db_session.add(
        KnowledgeChunk(
            id="bpom_test_arbutin", title="Alpha-Arbutin",
            regulation="Peraturan BPOM No. 17 Tahun 2022",
            appendix="Lampiran II", clause_entry="Pencerah",
            category="brightening", substance_name="Alpha-Arbutin",
            inci_name="Alpha-Arbutin", synonyms=["Alpha Arbutin"],
            max_concentration_pct=2.0,
            raw_text="Alpha-Arbutin maksimum 2,0% untuk krim wajah.",
        )
    )
    db_session.commit()


def payload(items):
    return {
        "formula_name": "Test Cream",
        "category": "Leave-On",
        "ingredients": [
            {
                "name": inci, "inci": inci, "smiles": "O",
                "weight_pct": pct, "phase": "D", "role": "active",
            }
            for inci, pct in items
        ],
    }


def audit(client, items, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(
            compliance_service, "get_groq_gateway", lambda: FakeGateway()
        )
    return client.post("/api/v1/compliance/audit", json=payload(items))


def test_compliant_audit_shape(client, db_session, monkeypatch):
    seed(db_session)
    body = audit(client, [("Phenoxyethanol", 0.8), ("Aqua", 99.2)], monkeypatch).json()
    assert body["overall_status"] == "COMPLIANT"
    assert body["audit_id"].startswith("audit_rag_")
    assert body["compliance_score"] == 1.0
    assert body["halal_status"] == "HALAL_CERTIFIED"
    assert body["total_tkdn_pct"] == 99.2
    assert "BPOM" in body["summary_verdict"]
    phenoxy = [a for a in body["ingredients_audit"] if a["inci"] == "Phenoxyethanol"][0]
    assert phenoxy["status"] == "PASSED"
    assert phenoxy["bpom_limit_pct"] == 1.0
    assert phenoxy["rag_citation"]["appendix"] == "Lampiran V"
    assert phenoxy["ingredient_id"].startswith("ing-")
    assert phenoxy["phase"] == "D"
    assert phenoxy["role"] == "active"
    assert "sejuk" in body["llm_reasoning"]["mandatory_label_warnings"][0]


def test_violation_and_synonym_resolution(client, db_session, monkeypatch):
    seed(db_session)
    body = audit(
        client,
        [("Phenoxyethanol", 1.2), ("Cocos Nucifera Oil", 3.0)],
        monkeypatch,
    ).json()
    assert body["overall_status"] == "NON_COMPLIANT"
    assert body["compliance_score"] == 0.7
    vco = [a for a in body["ingredients_audit"] if a["inci"] == "Cocos Nucifera Oil"][0]
    assert vco["tkdn_pct"] == 90.0
    assert body["total_tkdn_pct"] == 2.7


def test_llm_fallback_without_gateway(client, db_session, monkeypatch):
    seed(db_session)

    class DeadGateway:
        def chat_json(self, messages, model=None, max_tokens=1024):
            raise Exception("down")

    monkeypatch.setattr(compliance_service, "get_groq_gateway", lambda: DeadGateway())
    body = client.post(
        "/api/v1/compliance/audit", json=payload([("Aqua", 100.0)])
    ).json()
    assert body["overall_status"] == "COMPLIANT"
    assert body["llm_reasoning"]["local_substitution_recommendations"] == []


def test_ask_rag(client, db_session, monkeypatch):
    seed(db_session)
    monkeypatch.setattr(compliance_service, "get_groq_gateway", lambda: FakeGateway())
    r = client.post(
        "/api/v1/compliance/ask-rag",
        json={"query": "Apakah Alpha-Arbutin 2% aman?", "category_context": "Serum"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "Alpha-Arbutin" in body["answer"]
    assert body["citations"][0]["document"] == "Peraturan BPOM No. 17 Tahun 2022"
    assert body["confidence_score"] == 0.9
