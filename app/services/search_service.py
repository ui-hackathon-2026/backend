"""Ingredient search with Indonesian function keywords and synonyms.

Every query token must match either the ingredient text (name, INCI,
synonyms, description) or a function keyword mapped to its role.
Results rank by number of matched signals.
"""

import re

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.ingredient import Ingredient
from app.schemas.workbench import IngredientCatalogItem, IngredientListResponse
from app.services.workbench_service import to_catalog_item

FUNCTION_KEYWORDS = {
    "pengemulsi": "emulsifier",
    "emulgator": "emulsifier",
    "emulsifier": "emulsifier",
    "surfaktan": "emulsifier",
    "pelembab": "humectant",
    "humektan": "humectant",
    "humectant": "humectant",
    "pengental": "thickener",
    "thickener": "thickener",
    "polimer": "thickener",
    "pengawet": "preservative",
    "preservative": "preservative",
    "pelembut": "emollient",
    "emolien": "emollient",
    "emollient": "emollient",
    "tabir": "uv_filter",
    "sunscreen": "uv_filter",
    "surya": "uv_filter",
    "uv": "uv_filter",
    "antioksidan": "antioxidant",
    "antioxidant": "antioxidant",
    "pewangi": "fragrance",
    "parfum": "fragrance",
    "fragrance": "fragrance",
    "pelarut": "solvent",
    "solvent": "solvent",
    "air": "solvent",
    "ph": "ph_adjuster",
    "pengkelat": "chelating",
    "chelating": "chelating",
    "pencerah": "active",
    "aktif": "active",
    "active": "active",
}


def query_tokens(query: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]


def row_text(row: Ingredient) -> str:
    return " ".join(
        [
            row.name or "",
            row.inci,
            " ".join(row.synonyms or []),
            row.description or "",
        ]
    ).lower()


def search_ingredients(
    db: Session,
    q: str,
    phase: str | None = None,
    halal_only: bool = False,
    tkdn_min: float = 0.0,
    limit: int = 20,
) -> IngredientListResponse:
    try:
        rows = db.query(Ingredient).all()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    wants = query_tokens(q)
    if not wants:
        return IngredientListResponse(total=0, items=[])
    scored: list[tuple[int, Ingredient]] = []
    for row in rows:
        if phase and row.default_phase != phase.upper():
            continue
        if halal_only and row.halal_status != "HALAL":
            continue
        if (row.tkdn_pct or 0.0) < tkdn_min:
            continue
        text = row_text(row)
        score = 0
        for token in wants:
            hit_text = token in text
            hit_role = FUNCTION_KEYWORDS.get(token) == (row.default_role or "").lower()
            if hit_text:
                score += 2
            if hit_role:
                score += 3
        if score > 0:
            if row.inci.lower() in q.lower() or q.lower() in row.inci.lower():
                score += 5
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    items = [to_catalog_item(row) for _, row in scored[: max(1, min(limit, 100))]]
    return IngredientListResponse(total=len(scored), items=items)
