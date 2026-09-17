"""Internal formula similarity over ingredient sets and phase chassis.

Jaccard and cosine compare composition, chassis overlap compares the
four phase-fraction vectors. All deterministic, no embeddings needed.
"""

import math

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.formula import Formula
from app.models.ingredient import Ingredient
from app.schemas.knowledge import (
    SimilarityMatch,
    SimilarityRequest,
    SimilarityResponse,
)


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return round(len(left & right) / len(left | right), 3)


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    dot = sum(left.get(k, 0.0) * right.get(k, 0.0) for k in keys)
    norm_left = math.sqrt(sum(v * v for v in left.values()))
    norm_right = math.sqrt(sum(v * v for v in right.values()))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return round(dot / (norm_left * norm_right), 3)


def phase_vector(pairs) -> dict[str, float]:
    vector = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}
    for phase, weight in pairs:
        if phase in vector:
            vector[phase] += weight
    return vector


def check_similarity(db: Session, body: SimilarityRequest) -> SimilarityResponse:
    try:
        formulas = db.query(Formula).all()
        catalog_phases = {
            row.inci: row.default_phase for row in db.query(Ingredient).all()
        }
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    query_set = {i.inci for i in body.ingredients}
    query_weights = {i.inci: i.weight_pct for i in body.ingredients}
    query_phases = phase_vector(
        (catalog_phases[i.inci], i.weight_pct)
        for i in body.ingredients
        if i.inci in catalog_phases
    )
    matches: list[SimilarityMatch] = []
    for formula in formulas:
        stored_set = {i.inci for i in formula.ingredients}
        stored_weights = {i.inci: i.weight_pct for i in formula.ingredients}
        matches.append(
            SimilarityMatch(
                formula_id=formula.id,
                name=formula.name,
                jaccard=jaccard(query_set, stored_set),
                cosine=cosine(query_weights, stored_weights),
                chassis_overlap_pct=round(
                    cosine(
                        query_phases,
                        phase_vector(
                            (i.phase, i.weight_pct) for i in formula.ingredients
                        ),
                    )
                    * 100.0,
                    1,
                ),
            )
        )
    matches.sort(key=lambda m: (m.jaccard + m.cosine) / 2.0, reverse=True)
    return SimilarityResponse(matches=matches[:5])
