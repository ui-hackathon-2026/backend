"""External novelty against competitor label-ordered INCI lists.

Corpus ingredients carry rank order only, converted to pseudo-weights
with geometric decay. Estimates, never lab percentages. Products with
fewer than five ingredients stay out of the default comparison set.
"""

import math
import re

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.competitor import CompetitorProduct
from app.schemas.knowledge import (
    ExternalMatch,
    ExternalSimilarityRequest,
    ExternalSimilarityResponse,
)

DECAY_ALPHA = 0.75
MIN_INGREDIENTS = 5
FILTER_TOP_K = 25
RETURN_TOP = 5

SYNONYMS = {
    "water": "aqua",
    "eau": "aqua",
    "parfum": "fragrance",
}

_cache: list[dict] | None = None


def normalize_name(raw: str) -> str:
    cleaned = re.sub(r"[\u200b-\u200f\ufeff™®]", "", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return SYNONYMS.get(cleaned, cleaned)


def pseudo_weights(names: list[str]) -> dict[str, float]:
    weights = [DECAY_ALPHA**rank for rank in range(len(names))]
    total = sum(weights) or 1.0
    merged: dict[str, float] = {}
    for name, weight in zip(names, weights):
        merged[name] = merged.get(name, 0.0) + weight / total
    return merged


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    dot = sum(left.get(k, 0.0) * v for k, v in right.items())
    norm_left = math.sqrt(sum(v * v for v in left.values()))
    norm_right = math.sqrt(sum(v * v for v in right.values()))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return round(dot / (norm_left * norm_right), 3)


def load_corpus(db: Session) -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        rows = (
            db.query(CompetitorProduct)
            .filter(CompetitorProduct.ingredient_count >= MIN_INGREDIENTS)
            .all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    _cache = [
        {
            "product": row,
            "names": [normalize_name(n) for n in (row.inci_list or [])],
        }
        for row in rows
    ]
    for entry in _cache:
        entry["weights"] = pseudo_weights(entry["names"])
        entry["name_set"] = set(entry["names"])
    return _cache


def check_external(
    db: Session, body: ExternalSimilarityRequest
) -> ExternalSimilarityResponse:
    corpus = load_corpus(db)
    query_names = [normalize_name(i.inci) for i in body.ingredients]
    query_set = set(query_names)
    query_weights = {n: i.weight_pct / 100.0 for n, i in zip(query_names, body.ingredients)}
    ranked = []
    for entry in corpus:
        overlap = query_set & entry["name_set"]
        if not overlap:
            continue
        jaccard = len(overlap) / len(query_set | entry["name_set"])
        ranked.append((jaccard, entry))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    shortlisted = ranked[:FILTER_TOP_K]
    scored = []
    for _, entry in shortlisted:
        similarity = cosine(query_weights, entry["weights"])
        shared = sorted(query_set & entry["name_set"])
        scored.append((similarity, entry, shared))
    scored.sort(key=lambda triple: triple[0], reverse=True)
    top = scored[:RETURN_TOP]
    best = top[0][0] if top else 0.0
    return ExternalSimilarityResponse(
        novelty_score=round(1.0 - best, 3),
        estimated_basis="label-order pseudo-weights, not lab percentages",
        top_matches=[
            ExternalMatch(
                brand=entry["product"].brand,
                product_name=entry["product"].name,
                url=entry["product"].url,
                similarity=similarity,
                shared_ingredients=shared[:10],
            )
            for similarity, entry, shared in top
        ],
    )
