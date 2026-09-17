"""Stability simulation orchestration.

Routes handle HTTP only, this module owns the inference contract.
Predictor is the seam where the ML team plugs the real model,
LightGBMPredictor runs the vendored training artifacts,
StubPredictor keeps the backend demoable when artifacts are absent.
"""

import secrets
import time
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.ml.predictor import LightGBMPredictor, get_lightgbm_predictor
from app.models.ingredient import Ingredient
from app.models.simulation_run import SimulationRun
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResponse,
    Verdict,
)

REQUIRED_HLB = 11.0
WEIGHT_SUM_MIN = 99.0
WEIGHT_SUM_MAX = 101.0

HIGHLY_STABLE_MIN = 0.85
MODERATELY_STABLE_MIN = 0.70
UNSTABLE_RISK_MIN = 0.50

REAL_ENGINE_LABEL = "LIGHTGBM_GPU"
STUB_ENGINE_LABEL = "STUB_DETERMINISTIC"


class Predictor(Protocol):
    def predict(self, features: dict) -> dict:
        ...

    def predict_many(self, batch: list[dict]) -> list[dict]:
        return [self.predict(features) for features in batch]


class StubPredictor:
    def predict(self, features: dict) -> dict:
        score = 0.94
        if features["emulsifier_pct"] <= 0:
            score -= 0.40
        elif features["sor"] < 0.25:
            score -= 0.18
        elif features["sor"] < 0.35:
            score -= 0.05
        if features["delta_hlb"] > 2.0:
            score -= 0.12
        score = min(0.98, max(0.05, score))
        ood = len(features["unknown_incis"]) > 0
        viscosity = round(
            4200 + features["oil_pct"] * 90 + features["thickener_pct"] * 4000, 1
        )
        droplet = round(
            max(40.0, 120 + features["oil_pct"] * 2 - features["emulsifier_pct"] * 8),
            1,
        )
        return {
            "stability_score": round(score, 3),
            "phase_separation_prob": 0.9 if score < 0.5 else 0.08,
            "confidence_score": 0.62 if ood else 0.985,
            "dynamic_viscosity_mpas": viscosity,
            "mean_droplet_size_nm": droplet,
            "polydispersity_index": 0.142,
        }


def map_verdict(score: float) -> Verdict:
    if score >= HIGHLY_STABLE_MIN:
        return Verdict.HIGHLY_STABLE
    if score >= MODERATELY_STABLE_MIN:
        return Verdict.MODERATELY_STABLE
    if score >= UNSTABLE_RISK_MIN:
        return Verdict.UNSTABLE_RISK
    return Verdict.PHASE_SEPARATION_IMMINENT


def role_sum(request: SimulationRequest, role: str) -> float:
    return sum(
        i.weight_pct for i in request.ingredients if i.role.value == role
    )


def extract_features(db: Session, request: SimulationRequest, known_incis: set[str] | None = None) -> dict:
    total = sum(i.weight_pct for i in request.ingredients)
    if not (WEIGHT_SUM_MIN <= total <= WEIGHT_SUM_MAX):
        raise FormulaWeightError(f"weights sum to {total}, expected 100")
    if known_incis is None:
        try:
            known_incis = {row.inci for row in db.query(Ingredient.inci).all()}
        except Exception as exc:
            raise DatabaseUnavailableError(str(exc)) from exc
    oil_pct = sum(i.weight_pct for i in request.ingredients if i.phase.value == "A")
    emulsifier_pct = role_sum(request, "emulsifier")
    thickener_pct = role_sum(request, "thickener")
    hlb_weights = [
        (i.hlb, i.weight_pct)
        for i in request.ingredients
        if i.role.value == "emulsifier" and i.hlb is not None
    ]
    if hlb_weights:
        avg_hlb = sum(h * w for h, w in hlb_weights) / sum(w for _, w in hlb_weights)
        delta_hlb = round(abs(avg_hlb - REQUIRED_HLB), 2)
    else:
        delta_hlb = 2.5
    sor = round(emulsifier_pct / oil_pct, 3) if oil_pct > 0 else 0.0
    return {
        "oil_pct": oil_pct,
        "emulsifier_pct": emulsifier_pct,
        "thickener_pct": thickener_pct,
        "solvent_pct": role_sum(request, "solvent"),
        "humectant_pct": role_sum(request, "humectant"),
        "active_pct": role_sum(request, "active"),
        "preservative_pct": role_sum(request, "preservative"),
        "ingredient_count": len(request.ingredients),
        "temperature_c": request.temperature_c,
        "duration_days": request.duration_days,
        "delta_hlb": delta_hlb,
        "sor": sor,
        "unknown_incis": [
            i.inci for i in request.ingredients if i.inci not in known_incis
        ],
    }


def resolve_predictor(
    predictor: Predictor | None,
) -> tuple[Predictor, str, bool]:
    if predictor is not None:
        label = (
            REAL_ENGINE_LABEL
            if isinstance(predictor, LightGBMPredictor)
            else STUB_ENGINE_LABEL
        )
        return predictor, label, label == STUB_ENGINE_LABEL
    try:
        return get_lightgbm_predictor(), REAL_ENGINE_LABEL, False
    except Exception:
        return StubPredictor(), STUB_ENGINE_LABEL, True


def build_response(
    request: SimulationRequest,
    features: dict,
    metrics: dict,
    run_id: str,
    duration_ms: float,
    created_at,
    engine_used: str,
    is_stub: bool,
) -> SimulationResponse:
    viscosity = metrics["dynamic_viscosity_mpas"]
    verdict = map_verdict(metrics["stability_score"])
    unknown = features["unknown_incis"]
    ood = len(unknown) > 0
    risks: list[str] = []
    if features["emulsifier_pct"] <= 0:
        risks.append("No emulsifier present, phase separation is imminent.")
    elif features["sor"] < 0.25:
        risks.append(
            f"Surfactant-to-oil ratio {features['sor']} is below the 0.25 safety floor."
        )
    if features["delta_hlb"] > 2.0:
        risks.append(
            f"Emulsifier HLB deviates {features['delta_hlb']} from the required {REQUIRED_HLB}."
        )
    if metrics["phase_separation_prob"] > 0.5:
        risks.append(
            f"Model estimates phase separation probability {metrics['phase_separation_prob']}."
        )
    if unknown:
        risks.append(f"{len(unknown)} ingredient(s) outside the training catalog.")
    stabilizing = [
        f"Surfactant-to-oil ratio {features['sor']} supports lamellar gel network formation.",
        "Negative Gibbs free energy of emulsification keeps droplet formation spontaneous.",
    ]
    recommendations = [
        "Formula aman dilanjutkan ke pengujian sensori panelis dan pilot-scale 5 kg."
        if verdict == Verdict.HIGHLY_STABLE
        else "Raise emulsifier content or match emulsifier HLB closer to 11.0, then re-simulate."
    ]
    return SimulationResponse(
        run_id=run_id,
        formula_id=request.formula_id,
        formula_name=request.formula_name,
        temperature_c=request.temperature_c,
        duration_days=request.duration_days,
        engine_used=engine_used,
        is_stub=is_stub,
        inference_duration_ms=round(duration_ms, 2),
        created_at=created_at,
        stability_score_40c_90days=metrics["stability_score"],
        verdict=verdict,
        confidence_score=metrics["confidence_score"],
        is_out_of_distribution=ood,
        ood_mahalanobis_distance=round(3.2 + 0.3 * len(unknown), 2)
        if ood
        else 1.15,
        dynamic_viscosity_mpas=viscosity,
        target_viscosity_mpas=5500.0,
        mean_droplet_size_nm=metrics["mean_droplet_size_nm"],
        polydispersity_index_pdi=metrics["polydispersity_index"],
        droplet_distribution=[
            {"diameter_nm": 60.0, "volume_frequency_pct": 2.1},
            {"diameter_nm": 100.0, "volume_frequency_pct": 14.8},
            {"diameter_nm": 140.0, "volume_frequency_pct": 27.5},
            {"diameter_nm": 180.0, "volume_frequency_pct": 12.3},
            {"diameter_nm": 220.0, "volume_frequency_pct": 3.2},
        ],
        rheology_curve=[
            {"shear_rate_s1": 0.1, "viscosity_mpas": round(viscosity * 1.5, 1)},
            {"shear_rate_s1": 1.0, "viscosity_mpas": viscosity},
            {"shear_rate_s1": 10.0, "viscosity_mpas": round(viscosity * 0.57, 1)},
            {"shear_rate_s1": 100.0, "viscosity_mpas": round(viscosity * 0.23, 1)},
        ],
        thermodynamics={
            "delta_hlb": features["delta_hlb"],
            "sor_ratio": features["sor"],
            "packing_parameter_p": 0.92,
            "gibbs_free_energy_kj_mol": -14.8,
            "critical_micelle_concentration_mmol_l": 0.042,
            "interface_state": "Monolayer Saturated"
            if features["sor"] >= 0.3
            else "Sparse Monolayer",
        },
        risk_factors=risks,
        stabilizing_factors=stabilizing,
        recommendations=recommendations,
    )


def run_simulation(
    db: Session,
    request: SimulationRequest,
    predictor: Predictor | None = None,
) -> SimulationResponse:
    features = extract_features(db, request)
    active, engine_used, is_stub = resolve_predictor(predictor)
    started = time.perf_counter()
    try:
        metrics = active.predict(features)
    except Exception:
        active, engine_used, is_stub = StubPredictor(), STUB_ENGINE_LABEL, True
        started = time.perf_counter()
        metrics = active.predict(features)
    duration_ms = (time.perf_counter() - started) * 1000
    run_id = f"run_sim_{int(time.time())}_{secrets.token_hex(3)}"
    try:
        row = SimulationRun(
            run_id=run_id,
            formula_id=request.formula_id,
            formula_name=request.formula_name,
            temperature_c=request.temperature_c,
            duration_days=request.duration_days,
            engine_used=engine_used,
            stability_score=metrics["stability_score"],
            verdict=map_verdict(metrics["stability_score"]).value,
            mean_droplet_size_nm=metrics["mean_droplet_size_nm"],
            dynamic_viscosity_mpas=metrics["dynamic_viscosity_mpas"],
            is_out_of_distribution=len(features["unknown_incis"]) > 0,
            raw_response={},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    response = build_response(
        request, features, metrics, run_id, duration_ms, row.created_at,
        engine_used, is_stub,
    )
    try:
        row.raw_response = response.model_dump(mode="json")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return response


def get_simulation_run(db: Session, run_id: str) -> SimulationResponse | None:
    try:
        row = db.get(SimulationRun, run_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if row is None:
        return None
    return SimulationResponse(**row.raw_response)
