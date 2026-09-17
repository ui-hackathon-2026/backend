import numpy as np

import app.services.nsga_service as nsga_service
from app.services.nsga_service import assign_ranks, hypervolume, pareto_mask


class FakeGateway:
    def chat_json(self, messages, model=None, max_tokens=1024):
        return {
            "tradeOffSummary": "Ringkasan uji.",
            "physicochemicalRationale": "Rasional uji.",
        }


def test_pareto_mask_correctness():
    stability = np.array([0.9, 0.8, 0.7])
    cogs = np.array([10.0, 5.0, 20.0])
    tkdn = np.array([50.0, 60.0, 40.0])
    viscdev = np.array([0.1, 0.1, 0.5])
    assert pareto_mask(stability, cogs, tkdn, viscdev).tolist() == [True, True, False]
    assert assign_ranks(stability, cogs, tkdn, viscdev).tolist() == [1, 1, 2]
    optimal = pareto_mask(stability, cogs, tkdn, viscdev)
    assert 0.0 <= hypervolume(stability, cogs, tkdn, viscdev, optimal) <= 1.0


def test_run_nsga2_shape(client, db_session, monkeypatch):
    monkeypatch.setattr(nsga_service, "get_groq_gateway", lambda: FakeGateway())
    r = client.post(
        "/api/v1/optimizer/run-nsga2?seed=5",
        json={
            "weights": {"stabilityWeight": 35, "cogsWeight": 30, "tkdnWeight": 20, "viscosityWeight": 15},
            "constraints": {"minStabilityPct": 0, "maxCogsIdrPerKg": 10000000, "minTkdnPct": 0, "targetViscosityMpaS": 5200},
            "preset": "balanced",
            "trialsCount": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["trialsEvaluated"] == 30
    assert len(body["points"]) == 30
    assert body["nonDominatedCount"] >= 1
    assert 0.0 <= body["hypervolumeScore"] <= 1.0
    assert len(body["topCandidates"]) == 3
    assert [c["id"] for c in body["topCandidates"]] == ["A", "B", "C"]
    candidate_ids = {p["candidateId"] for p in body["points"] if p["candidateId"]}
    assert candidate_ids == {"A", "B", "C"}
    first = body["topCandidates"][0]
    assert first["badgeLabel"] == "Rekomendasi Utama"
    assert first["tradeOffSummary"] == "Ringkasan uji."
    assert len(first["ingredients"]) > 0
    assert abs(sum(i["weightPct"] for i in first["ingredients"]) - 100.0) < 0.06


def test_infeasible_constraints_422(client, db_session, monkeypatch):
    monkeypatch.setattr(nsga_service, "get_groq_gateway", lambda: FakeGateway())
    r = client.post(
        "/api/v1/optimizer/run-nsga2?seed=5",
        json={
            "constraints": {"minStabilityPct": 100, "maxCogsIdrPerKg": 1, "minTkdnPct": 100, "targetViscosityMpaS": 5200},
            "trialsCount": 10,
        },
    )
    assert r.status_code == 422
    assert "suggestions" in r.json()["detail"]
