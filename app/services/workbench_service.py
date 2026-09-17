"""Workbench catalog read, instant physicochemical moments, draft save.

Moments compute purely from request numbers. Draft save reuses the
canonical formula storage through an adapter over the flat workbench shape.
"""

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.models.formula import Formula
from app.models.ingredient import Ingredient
from app.schemas.formula import FormulaCreate, FormulaPhases, FormulaIngredientInput
from app.schemas.workbench import (
    FormulaCompositionDto,
    FormulaMomentsDto,
    IngredientCatalogItem,
    IngredientListResponse,
    MomentWarning,
    RadarMetrics,
    WorkbenchSaveRequest,
    WorkbenchSaveResponse,
)
from app.services.formula_service import WEIGHT_SUM_MAX, WEIGHT_SUM_MIN, create_formula

REQUIRED_HLB = 11.0
WEIGHT_ERROR_MESSAGE = "Total formula concentration must sum to 100% ± 1.0%"


def slug(inci: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", inci.lower()).strip("-")


def to_catalog_item(row: Ingredient) -> IngredientCatalogItem:
    return IngredientCatalogItem(
        id=f"cat-{slug(row.inci)}",
        name=row.name,
        inci=row.inci,
        smiles=row.smiles,
        cas_number=row.cas_number,
        default_phase=row.default_phase,
        role=row.default_role,
        hlb=row.hlb,
        default_weight_pct=row.default_weight_pct or 0.0,
        min_recommended_pct=row.min_recommended_pct,
        max_recommended_pct=row.max_recommended_pct,
        bpom_limit_pct=row.bpom_limit_pct,
        is_halal=row.halal_status == "HALAL",
        tkdn_pct=row.tkdn_pct or 0.0,
        cost_per_kg_idr=row.cost_per_kg_idr or 0.0,
        description=row.description,
    )


def list_ingredients(
    db: Session,
    phase: str | None = None,
    role: str | None = None,
    q: str | None = None,
    halal_only: bool = False,
) -> IngredientListResponse:
    try:
        query = db.query(Ingredient)
        if phase:
            query = query.filter(Ingredient.default_phase == phase.upper())
        if role:
            query = query.filter(Ingredient.default_role == role.lower())
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Ingredient.name.ilike(like),
                    Ingredient.inci.ilike(like),
                    Ingredient.smiles.ilike(like),
                )
            )
        if halal_only:
            query = query.filter(Ingredient.halal_status == "HALAL")
        rows = query.order_by(Ingredient.name).all()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    items = [to_catalog_item(r) for r in rows]
    return IngredientListResponse(total=len(items), items=items)


def clamp01(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 3)


def calculate_moments(body: FormulaCompositionDto) -> FormulaMomentsDto:
    total = round(sum(i.weight_pct for i in body.ingredients), 2)
    if not (WEIGHT_SUM_MIN <= total <= WEIGHT_SUM_MAX):
        raise FormulaWeightError(WEIGHT_ERROR_MESSAGE)
    oil = sum(i.weight_pct for i in body.ingredients if i.phase == "A")
    emulsifier = sum(i.weight_pct for i in body.ingredients if i.role == "emulsifier")
    thickener = sum(i.weight_pct for i in body.ingredients if i.role == "thickener")
    hlb_weights = [(i.hlb, i.weight_pct) for i in body.ingredients if i.role == "emulsifier" and i.hlb is not None]
    if hlb_weights:
        system_hlb = round(sum(h * w for h, w in hlb_weights) / sum(w for _, w in hlb_weights), 2)
    else:
        system_hlb = 0.0
    delta_hlb = round(abs(system_hlb - REQUIRED_HLB), 2) if hlb_weights else round(REQUIRED_HLB, 2)
    sor = round(emulsifier / oil, 4) if oil > 0 else 0.0
    phase_totals = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}
    for i in body.ingredients:
        if i.phase in phase_totals:
            phase_totals[i.phase] = round(phase_totals[i.phase] + i.weight_pct, 2)
    cogs = round(sum(i.weight_pct / 100.0 * i.cost_per_kg_idr for i in body.ingredients), 0)
    tkdn = round(sum(i.weight_pct / 100.0 * i.tkdn_pct for i in body.ingredients), 1)
    warnings: list[MomentWarning] = []
    if emulsifier <= 0:
        warnings.append(MomentWarning(code="NO_EMULSIFIER", severity="error", message="No emulsifier present, the emulsion cannot form."))
    elif sor < 0.25:
        warnings.append(MomentWarning(code="SOR_LOW", severity="warning", message=f"Surfactant-to-oil ratio ({sor}) is below the 0.25 safety floor."))
    if hlb_weights and delta_hlb > 2.0:
        warnings.append(MomentWarning(code="HLB_MISMATCH", severity="warning", message=f"Delta HLB ({delta_hlb}) is high. Consider adding a lipophilic co-surfactant."))
    return FormulaMomentsDto(
        system_hlb=system_hlb,
        required_hlb=REQUIRED_HLB,
        delta_hlb=delta_hlb,
        sor_ratio=sor,
        phase_totals=phase_totals,
        total_weight_pct=total,
        estimated_cogs_per_kg_idr=cogs,
        overall_tkdn_pct=tkdn,
        radar_metrics=RadarMetrics(
            hlb_equilibrium=clamp01(1 - delta_hlb / 10),
            surfactant_efficiency=clamp01(sor / 0.4),
            viscosity_potential=clamp01(thickener / 2 + emulsifier / 10 + oil / 100),
            cost_efficiency=clamp01(1 - cogs / 200000),
            tkdn_score=clamp01(tkdn / 100),
        ),
        warnings=warnings,
    )


def save_draft(db: Session, body: WorkbenchSaveRequest, owner_id: int | None = None) -> WorkbenchSaveResponse:
    total = round(sum(i.weight_pct for i in body.ingredients), 2)
    if not (WEIGHT_SUM_MIN <= total <= WEIGHT_SUM_MAX):
        raise FormulaWeightError(WEIGHT_ERROR_MESSAGE)
    groups: dict[str, list[FormulaIngredientInput]] = {"A": [], "B": [], "C": [], "D": []}
    for i in body.ingredients:
        phase = i.phase.upper()
        if phase not in groups:
            raise FormulaWeightError(f"unknown phase {i.phase}")
        groups[phase].append(
            FormulaIngredientInput(
                inci=i.inci, name=i.name, smiles=i.smiles,
                weight_pct=i.weight_pct, is_locked=i.is_locked,
            )
        )
    created = create_formula(
        db,
        FormulaCreate(
            name=body.name,
            category=body.category,
            batch_size_g=body.batch_size_g,
            notes=body.notes,
            project_id=body.project_id,
            phases=FormulaPhases(
                phase_a=groups["A"], phase_b=groups["B"],
                phase_c=groups["C"], phase_d=groups["D"],
            ),
        ),
        owner_id=owner_id,
    )
    try:
        row = db.get(Formula, created.formula_id)
        created_at = row.created_at.isoformat() if row else created.updated_at.isoformat()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return WorkbenchSaveResponse(
        id=created.formula_id,
        name=created.name,
        category=created.category,
        batch_size_g=created.batch_size_g,
        created_at=created_at,
        updated_at=created.updated_at.isoformat(),
    )
