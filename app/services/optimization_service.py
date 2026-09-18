"""Greedy random-search optimizer over the mass simplex.

Each trial samples a recipe honoring locked ingredients, all trials are
scored in one vectorized surrogate batch plus catalog cost and TKDN, and
the top three are returned. Deterministic given seed.
"""

import random
import secrets
import time

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.models.catalog import OptimizationJob
from app.models.ingredient import Ingredient
from app.schemas.optimize import (
    OptimizeRequest,
    OptimizeResponse,
    ScatterPoint,
    TopCandidate,
)
from app.schemas.simulation import IngredientInput, SimulationRequest
from app.services.simulation_service import StubPredictor, extract_features

POOL = [
    ("Caprylic/Capric Triglyceride", "A", "emollient", None),
    ("Dimethicone", "A", "emollient", None),
    ("Squalane", "A", "emollient", None),
    ("Virgin Coconut Oil", "A", "emollient", None),
    ("Ethylhexyl Methoxycinnamate", "A", "uv_filter", None),
    ("Aqua", "B", "solvent", None),
    ("Glycerin", "B", "humectant", None),
    ("Butylene Glycol", "B", "humectant", None),
    ("Glyceryl Stearate", "C", "emulsifier", 3.8),
    ("Polysorbate 60", "C", "emulsifier", 14.9),
    ("Niacinamide", "D", "active", None),
    ("Panthenol", "D", "active", None),
    ("Tocopheryl Acetate", "A", "active", None),
    ("Phenoxyethanol", "D", "preservative", None),
]

MAX_COGS_NORM = 1000000.0


DEFAULT_COSTS = {
    "Aqua": 2500.0,
    "Caprylic/Capric Triglyceride": 85000.0,
    "Dimethicone": 120000.0,
    "Squalane": 380000.0,
    "Virgin Coconut Oil": 65000.0,
    "Ethylhexyl Methoxycinnamate": 210000.0,
    "Glycerin": 45000.0,
    "Butylene Glycol": 95000.0,
    "Glyceryl Stearate": 110000.0,
    "Polysorbate 60": 130000.0,
    "Niacinamide": 220000.0,
    "Panthenol": 350000.0,
    "Tocopheryl Acetate": 280000.0,
    "Phenoxyethanol": 160000.0,
}

DEFAULT_TKDN = {
    "Aqua": 100.0,
    "Virgin Coconut Oil": 95.0,
    "Glycerin": 80.0,
    "Caprylic/Capric Triglyceride": 65.0,
    "Glyceryl Stearate": 55.0,
    "Squalane": 45.0,
    "Polysorbate 60": 25.0,
    "Dimethicone": 0.0,
    "Ethylhexyl Methoxycinnamate": 0.0,
    "Butylene Glycol": 0.0,
    "Niacinamide": 0.0,
    "Panthenol": 0.0,
    "Tocopheryl Acetate": 0.0,
    "Phenoxyethanol": 0.0,
}


def catalog_maps(db: Session) -> tuple[dict, dict, set[str]]:
    try:
        rows = db.query(Ingredient).all()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    cost = {**DEFAULT_COSTS, **{r.inci: r.cost_per_kg_idr for r in rows if r.cost_per_kg_idr is not None}}
    tkdn = {**DEFAULT_TKDN, **{r.inci: r.tkdn_pct for r in rows if r.tkdn_pct is not None}}
    known = {r.inci for r in rows} | set(DEFAULT_COSTS.keys())
    return cost, tkdn, known


def sample_recipe(
    rng: random.Random,
    locked: dict[str, float],
    pool: list[str],
    cost: dict | None = None,
) -> dict[str, float]:
    locked_total = sum(locked.values())
    if locked_total >= 100.0:
        raise FormulaWeightError("locked ingredients already reach 100%")
    recipe = dict(locked)
    free_total = 100.0 - locked_total
    rest = list(pool)
    if "Aqua" in rest:
        aqua_share = round(min(rng.uniform(55.0, 85.0), free_total * 0.92), 2)
        recipe["Aqua"] = aqua_share
        free_total = round(100.0 - sum(recipe.values()), 2)
        rest = [inci for inci in rest if inci != "Aqua"]
    draws = []
    for inci in rest:
        price = (cost or {}).get(inci, 0.0)
        draws.append((rng.random() + 0.05) / (1.0 + price / 100000.0))
    for inci, draw in zip(rest, draws):
        recipe[inci] = round(draw / sum(draws) * free_total, 2)
    diff = round(100.0 - sum(recipe.values()), 2)
    recipe[rest[-1]] = round(recipe[rest[-1]] + diff, 2)
    return recipe


def recipe_features(
    db: Session, recipe: dict[str, float], known: set[str]
) -> dict:
    ingredients = []
    for inci, pct in recipe.items():
        meta = next((p for p in POOL if p[0] == inci), ("", "B", "active", None))
        phase, role, hlb = meta[1], meta[2], meta[3]
        ingredients.append(
            IngredientInput(
                name=inci, inci=inci, smiles="O", weight_pct=pct,
                phase=phase, role=role, hlb=hlb,
            )
        )
    request = SimulationRequest(formula_name="trial", ingredients=ingredients)
    return extract_features(db, request, known_incis=known)


def assemble_trial(recipe, metrics, cost, tkdn, objectives) -> dict:
    cogs = sum(pct / 100.0 * cost.get(inci, 0.0) for inci, pct in recipe.items())
    tkdn_score = sum(pct / 100.0 * tkdn.get(inci, 0.0) for inci, pct in recipe.items())
    visc_pen = abs(metrics["dynamic_viscosity_mpas"] - objectives.target_viscosity_mpas) / objectives.target_viscosity_mpas
    composite = (
        objectives.maximize_stability * metrics["stability_score"]
        - objectives.minimize_cogs * (cogs / MAX_COGS_NORM)
        + objectives.maximize_tkdn * (tkdn_score / 100.0)
        - 0.2 * min(visc_pen, 2.0)
    )
    return {
        "recipe": recipe,
        "stability": metrics["stability_score"],
        "cogs": round(cogs, 0),
        "tkdn": round(tkdn_score, 1),
        "viscosity": metrics["dynamic_viscosity_mpas"],
        "composite": composite,
    }


def run_optimization(
    db: Session, body: OptimizeRequest, seed: int | None = None,
    max_cogs: float | None = None,
) -> OptimizeResponse:
    from app.ml.predictor import get_lightgbm_predictor

    try:
        predictor = get_lightgbm_predictor()
    except Exception:
        predictor = StubPredictor()
    cost, tkdn, known = catalog_maps(db)
    rng = random.Random(seed)
    locked = {i.inci: i.pct for i in body.locked_ingredients}
    pool = [inci for inci, _, _, _ in POOL if inci not in locked]
    started = time.perf_counter()
    recipes = [sample_recipe(rng, locked, pool, cost) for _ in range(body.num_trials)]
    batch = [recipe_features(db, recipe, known) for recipe in recipes]
    try:
        metrics_list = predictor.predict_many(batch)
    except Exception:
        fallback = StubPredictor()
        metrics_list = fallback.predict_many(batch)
    trials = [
        assemble_trial(recipe, metrics, cost, tkdn, body.target_objectives)
        for recipe, metrics in zip(recipes, metrics_list)
    ]
    duration = time.perf_counter() - started
    eligible = [t for t in trials if max_cogs is None or t["cogs"] <= max_cogs]
    ranked = eligible if eligible else trials
    by_stability = sorted(ranked, key=lambda t: t["stability"], reverse=True)
    by_composite = sorted(trials, key=lambda t: t["composite"], reverse=True)
    by_tkdn = sorted(trials, key=lambda t: t["tkdn"], reverse=True)
    top = [
        TopCandidate(label="Candidate A (Max Stability)", stability=by_stability[0]["stability"], cogs_idr_per_kg=by_stability[0]["cogs"], tkdn_pct=by_stability[0]["tkdn"], recipe=by_stability[0]["recipe"]),
        TopCandidate(label="Candidate B (Sweet Spot)", stability=by_composite[0]["stability"], cogs_idr_per_kg=by_composite[0]["cogs"], tkdn_pct=by_composite[0]["tkdn"], recipe=by_composite[0]["recipe"]),
        TopCandidate(label="Candidate C (Local Botanical Hero)", stability=by_tkdn[0]["stability"], cogs_idr_per_kg=by_tkdn[0]["cogs"], tkdn_pct=by_tkdn[0]["tkdn"], recipe=by_tkdn[0]["recipe"]),
    ]
    experiment_id = f"exp_{secrets.token_hex(6)}"
    response = OptimizeResponse(
        experiment_id=experiment_id,
        total_evaluated=len(trials),
        duration_seconds=round(duration, 2),
        top_candidates=top,
        scatter_3d=[
            ScatterPoint(x=t["stability"], y=t["cogs"], z=t["tkdn"], id=f"t{i}")
            for i, t in enumerate(trials)
        ],
    )
    try:
        db.add(
            OptimizationJob(
                id=experiment_id,
                params=body.model_dump(mode="json"),
                result=response.model_dump(mode="json"),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return response


def get_optimization(db: Session, experiment_id: str) -> OptimizeResponse | None:
    try:
        row = db.get(OptimizationJob, experiment_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if row is None:
        return None
    return OptimizeResponse(**row.result)
