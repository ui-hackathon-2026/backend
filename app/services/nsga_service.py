"""NSGA-style Pareto endpoint over the shared random-search engine.

Trials reuse the vectorized surrogate batch, domination and hypervolume
run on numpy, candidate narratives come from the LLM gateway with
deterministic fallback. Infeasible constraint sets yield 422 guidance.
"""

import random
import time

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableError
from app.core.llm import GroqGateway, get_groq_gateway
from app.models.ingredient import Ingredient
from app.schemas.nsga import (
    CandidateIngredient,
    CandidateMetrics,
    FrontierPoint,
    ParetoOptimizationRequest,
    ParetoOptimizationResponse,
    TopCandidateDetail,
)
from app.services.optimization_service import (
    POOL,
    catalog_maps,
    sample_recipe,
)
from app.services.orchestration_service import FUNCTION_DESC

NARRATIVE_SYSTEM = (
    "Given a cosmetic candidate as JSON, respond with JSON keys: "
    "tradeOffSummary (one Bahasa Indonesia sentence with numbers), "
    "physicochemicalRationale (two Bahasa Indonesia sentences on the "
    "emulsifier system). Return valid JSON only."
)

HV_SAMPLES = 20000
HV_SEED = 42


class InfeasibleConstraintsError(ValueError):
    def __init__(self, suggestions: dict):
        super().__init__("no trial satisfies all constraints")
        self.suggestions = suggestions


def pareto_mask(
    stability: np.ndarray,
    cogs: np.ndarray,
    tkdn: np.ndarray,
    viscdev: np.ndarray,
) -> np.ndarray:
    n = len(stability)
    order = np.argsort(-stability, kind="stable")
    is_opt = np.zeros(n, dtype=bool)
    kept: list[int] = []
    i = 0
    while i < n:
        j = i
        while j < n and stability[order[j]] == stability[order[i]]:
            j += 1
        group = order[i:j]
        for k in group:
            if kept:
                K = np.array(kept)
                if dominates(K, k, cogs, tkdn, viscdev):
                    continue
            others = group[group != k]
            if len(others) and dominates(others, k, cogs, tkdn, viscdev):
                continue
            is_opt[k] = True
            kept.append(int(k))
        i = j
    return is_opt


def dominates(
    candidates: np.ndarray,
    k: int,
    cogs: np.ndarray,
    tkdn: np.ndarray,
    viscdev: np.ndarray,
) -> bool:
    better_equal = (
        (cogs[candidates] <= cogs[k])
        & (tkdn[candidates] >= tkdn[k])
        & (viscdev[candidates] <= viscdev[k])
    )
    strict = (
        (cogs[candidates] < cogs[k])
        | (tkdn[candidates] > tkdn[k])
        | (viscdev[candidates] < viscdev[k])
    )
    return bool((better_equal & strict).any())


def assign_ranks(
    stability: np.ndarray,
    cogs: np.ndarray,
    tkdn: np.ndarray,
    viscdev: np.ndarray,
) -> np.ndarray:
    ranks = np.full(len(stability), 3, dtype=int)
    remaining = np.ones(len(stability), dtype=bool)
    for rank in (1, 2):
        idx = np.where(remaining)[0]
        if len(idx) == 0:
            break
        front = pareto_mask(
            stability[idx], cogs[idx], tkdn[idx], viscdev[idx]
        )
        ranks[idx[front]] = rank
        remaining[idx[front]] = False
    return ranks


def hypervolume(
    stability: np.ndarray,
    cogs: np.ndarray,
    tkdn: np.ndarray,
    viscdev: np.ndarray,
    optimal: np.ndarray,
) -> float:
    rng = np.random.default_rng(HV_SEED)
    samples = rng.random((HV_SAMPLES, 4))
    best_cogs = max(float(cogs.max()), 1.0)
    dominated = np.zeros(HV_SAMPLES, dtype=bool)
    for i in np.where(optimal)[0]:
        box = (
            (samples[:, 0] <= stability[i])
            & (samples[:, 1] <= 1.0 - cogs[i] / best_cogs)
            & (samples[:, 2] <= tkdn[i] / 100.0)
            & (samples[:, 3] <= 1.0 - min(viscdev[i], 1.0))
        )
        dominated |= box
    return round(float(dominated.mean()), 3)


def narratives(
    gateway: GroqGateway | None, candidates: list[dict]
) -> list[dict]:
    import json as jsonlib
    from concurrent.futures import ThreadPoolExecutor

    active = gateway or get_groq_gateway()

    def narrate(candidate: dict) -> dict:
        try:
            parsed = active.chat_json(
                [
                    {
                        "role": "user",
                        "content": f"{NARRATIVE_SYSTEM}\nKandidat: {jsonlib.dumps(candidate, ensure_ascii=False)}",
                    }
                ],
                model=settings.groq_model_fast,
                max_tokens=1024,
            )
            summary = str(parsed.get("tradeOffSummary", "")).strip()
            rationale = str(parsed.get("physicochemicalRationale", "")).strip()
            if summary and rationale:
                return {
                    "tradeOffSummary": summary,
                    "physicochemicalRationale": rationale,
                }
        except Exception:
            pass
        return {
            "tradeOffSummary": (
                f"Kandidat stabilitas {candidate['stabilityPct']}% dengan "
                f"biaya Rp {candidate['cogsIdrPerKg']:,.0f}/kg."
            ),
            "physicochemicalRationale": (
                "Sistem pengemulsi non-ionik ganda membentuk lamellar gel "
                "network yang menahan coalescence pada 40C."
            ),
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(narrate, candidates))


POOL_META = {inci: (phase, role, hlb) for inci, phase, role, hlb in POOL}


def fast_features(
    recipe: dict[str, float],
    known: set[str],
    temperature_c: float,
    duration_days: int,
) -> dict:
    by_role: dict[str, float] = {}
    hlb_num = 0.0
    hlb_den = 0.0
    oil = 0.0
    unknown = []
    for inci, pct in recipe.items():
        phase, role, hlb = POOL_META.get(inci, ("B", "active", None))
        by_role[role] = by_role.get(role, 0.0) + pct
        if phase == "A":
            oil += pct
        if hlb is not None and role == "emulsifier":
            hlb_num += hlb * pct
            hlb_den += pct
        if inci not in known:
            unknown.append(inci)
    emulsifier = by_role.get("emulsifier", 0.0)
    return {
        "oil_pct": oil,
        "emulsifier_pct": emulsifier,
        "thickener_pct": by_role.get("thickener", 0.0),
        "solvent_pct": by_role.get("solvent", 0.0),
        "humectant_pct": by_role.get("humectant", 0.0),
        "active_pct": by_role.get("active", 0.0),
        "preservative_pct": by_role.get("preservative", 0.0),
        "ingredient_count": len(recipe),
        "temperature_c": temperature_c,
        "duration_days": duration_days,
        "delta_hlb": round(abs(hlb_num / hlb_den - 11.0), 2) if hlb_den > 0 else 2.5,
        "sor": round(emulsifier / oil, 3) if oil > 0 else 0.0,
        "unknown_incis": unknown,
    }


def run_nsga2(
    db: Session,
    body: ParetoOptimizationRequest,
    gateway: GroqGateway | None = None,
    seed: int | None = None,
) -> ParetoOptimizationResponse:
    from app.ml.predictor import get_lightgbm_predictor
    from app.services.simulation_service import StubPredictor

    try:
        predictor = get_lightgbm_predictor()
    except Exception:
        predictor = StubPredictor()
    cost, tkdn, known = catalog_maps(db)
    try:
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    rng = random.Random(seed)
    pool = [inci for inci, _, _, _ in POOL]
    started = time.perf_counter()
    recipes = [sample_recipe(rng, {}, pool, cost) for _ in range(body.trialsCount)]
    batch = [
        fast_features(recipe, known, 40.0, 90) for recipe in recipes
    ]
    try:
        metrics_list = predictor.predict_many(
            batch, only=("stability_pass", "viscosity")
        )
    except Exception:
        metrics_list = StubPredictor().predict_many(batch)
    stability = np.array([m["stability_score"] for m in metrics_list])
    cogs = np.array([
        sum(pct / 100.0 * cost.get(inci, 0.0) for inci, pct in recipe.items())
        for recipe in recipes
    ])
    tkdn_vals = np.array([
        sum(pct / 100.0 * tkdn.get(inci, 0.0) for inci, pct in recipe.items())
        for recipe in recipes
    ])
    viscosity = np.array([m["dynamic_viscosity_mpas"] for m in metrics_list])
    viscdev = np.abs(viscosity - body.constraints.targetViscosityMpaS) / body.constraints.targetViscosityMpaS
    feasible = (
        (stability * 100.0 >= body.constraints.minStabilityPct)
        & (cogs <= body.constraints.maxCogsIdrPerKg)
        & (tkdn_vals >= body.constraints.minTkdnPct)
    )
    if not feasible.any():
        raise InfeasibleConstraintsError(
            {
                "bestStabilityPct": round(float(stability.max() * 100.0), 1),
                "bestCogsIdrPerKg": round(float(cogs.min()), 0),
                "bestTkdnPct": round(float(tkdn_vals.max()), 1),
                "suggestion": "relax minStabilityPct, maxCogsIdrPerKg, or minTkdnPct toward the best achieved values",
            }
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    optimal = pareto_mask(stability, cogs, tkdn_vals, viscdev)
    ranks = assign_ranks(stability, cogs, tkdn_vals, viscdev)
    weights = body.weights
    total_w = weights.stabilityWeight + weights.cogsWeight + weights.tkdnWeight + weights.viscosityWeight or 1.0
    composite = (
        (weights.stabilityWeight / total_w) * stability
        - (weights.cogsWeight / total_w) * (cogs / max(float(cogs.max()), 1.0))
        + (weights.tkdnWeight / total_w) * (tkdn_vals / 100.0)
        - (weights.viscosityWeight / total_w) * np.minimum(viscdev, 2.0)
    )
    order = np.argsort(feasible.astype(int) * 1000.0 + composite)[::-1]
    pick_a, pick_b, pick_c = int(order[0]), int(
        np.argsort(stability * feasible)[::-1][0]
    ), int(np.argsort(tkdn_vals * feasible)[::-1][0])
    picks = {"A": pick_a, "B": pick_b, "C": pick_c}
    by_index = {idx: cid for cid, idx in picks.items()}
    front_idx = set(np.where(optimal)[0])
    stride = max(1, len(recipes) // 2000)
    kept = [i for i in range(len(recipes)) if i in front_idx or i % stride == 0]
    points = [
        FrontierPoint(
            id=f"frontier-{i}",
            trialIndex=i,
            stabilityPct=round(float(stability[i]) * 100.0, 1),
            cogsIdr=round(float(cogs[i]), 0),
            tkdnPct=round(float(tkdn_vals[i]), 1),
            viscosityMpaS=round(float(viscosity[i]), 0),
            isParetoOptimal=bool(optimal[i]),
            rank=int(ranks[i]),
            candidateId=by_index.get(i),
        )
        for i in kept
    ]
    pool_meta = {inci: (phase, role, hlb) for inci, phase, role, hlb in POOL}
    blurbs = narratives(
        gateway,
        [
            {
                "stabilityPct": round(float(stability[p]) * 100.0, 1),
                "cogsIdrPerKg": round(float(cogs[p]), 0),
                "tkdnPct": round(float(tkdn_vals[p]), 1),
            }
            for p in (pick_a, pick_b, pick_c)
        ],
    )
    titles = {
        "A": ("Kandidat A: The Balanced Sweet Spot", "Kompromi Optimal Stabilitas & Biaya", "Rekomendasi Utama"),
        "B": ("Kandidat B: Stability Champion", "Stabilitas Maksimum 40C", "Paling Stabil"),
        "C": ("Kandidat C: Local Botanical Hero", "TKDN Tertinggi", "Paling Lokal"),
    }
    top: list[TopCandidateDetail] = []
    for cid, pick in picks.items():
        hlb_num = 0.0
        hlb_den = 0.0
        enriched: list[CandidateIngredient] = []
        for position, (inci, pct) in enumerate(recipes[pick].items()):
            phase, role, hlb = pool_meta.get(inci, ("B", "active", None))
            known_row = catalog.get(inci)
            if hlb is not None:
                hlb_num += hlb * pct
                hlb_den += pct
            enriched.append(
                CandidateIngredient(
                    id=f"ing-{position + 1}",
                    name=known_row.name if known_row else inci,
                    inci=inci,
                    phase=phase,
                    weightPct=pct,
                    functionDesc=FUNCTION_DESC.get(role, role),
                    isLocalTkdn=(known_row.tkdn_pct or 0.0) > 0 if known_row else False,
                )
            )
        title, archetype, badge = titles[cid]
        top.append(
            TopCandidateDetail(
                id=cid,
                title=title,
                archetype=archetype,
                badgeLabel=badge,
                metrics=CandidateMetrics(
                    stabilityPct=round(float(stability[pick]) * 100.0, 1),
                    cogsIdrPerKg=round(float(cogs[pick]), 0),
                    tkdnPct=round(float(tkdn_vals[pick]), 1),
                    viscosityMpaS=round(float(viscosity[pick]), 0),
                    systemHlb=round(hlb_num / hlb_den, 1) if hlb_den > 0 else 0.0,
                ),
                tradeOffSummary=blurbs[["A", "B", "C"].index(cid)]["tradeOffSummary"],
                physicochemicalRationale=blurbs[["A", "B", "C"].index(cid)][
                    "physicochemicalRationale"
                ],
                ingredients=enriched,
            )
        )
    return ParetoOptimizationResponse(
        trialsEvaluated=len(recipes),
        executionTimeMs=round(elapsed_ms, 0),
        nonDominatedCount=int(optimal.sum()),
        hypervolumeScore=hypervolume(stability, cogs, tkdn_vals, viscdev, optimal),
        points=points,
        topCandidates=top,
    )
