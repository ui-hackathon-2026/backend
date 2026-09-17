"""Formula CRUD with mass-balance validation and version snapshots.

Every update stores the previous ingredient set as a version before
replacing it, the version log is append-only.
"""

import secrets

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.models.formula import Formula, FormulaIngredient, FormulaVersion
from app.schemas.formula import (
    FormulaCreate,
    FormulaResponse,
    FormulaUpdate,
    FormulaVersionOutput,
)

VALID_BALANCED = "VALID_BALANCED"
WEIGHT_SUM_MIN = 99.0
WEIGHT_SUM_MAX = 101.0


def new_formula_id() -> str:
    return f"form_{secrets.token_hex(6)}"


def total_weight(items) -> float:
    return round(sum(i.weight_pct for _, i in items), 2)


def check_total(items) -> float:
    total = total_weight(items)
    if not (WEIGHT_SUM_MIN <= total <= WEIGHT_SUM_MAX):
        raise FormulaWeightError(f"weights sum to {total}, expected 100")
    return total


def to_response(formula: Formula, total: float) -> FormulaResponse:
    return FormulaResponse(
        formula_id=formula.id,
        name=formula.name,
        category=formula.category,
        batch_size_g=formula.batch_size_g,
        notes=formula.notes,
        project_id=formula.project_id,
        total_weight_pct=total,
        status=VALID_BALANCED,
        updated_at=formula.updated_at,
        ingredients=[
            {
                "inci": i.inci,
                "name": i.name,
                "smiles": i.smiles,
                "weight_pct": i.weight_pct,
                "phase": i.phase,
                "is_locked": i.is_locked,
            }
            for i in formula.ingredients
        ],
    )


def create_formula(db: Session, body: FormulaCreate) -> FormulaResponse:
    items = body.phases.flattened()
    total = check_total(items)
    try:
        formula = Formula(
            id=new_formula_id(),
            name=body.name,
            category=body.category,
            batch_size_g=body.batch_size_g,
            notes=body.notes,
            project_id=body.project_id,
        )
        db.add(formula)
        for phase, item in items:
            db.add(
                FormulaIngredient(
                    formula_id=formula.id,
                    phase=phase,
                    inci=item.inci,
                    name=item.name,
                    smiles=item.smiles,
                    weight_pct=item.weight_pct,
                    is_locked=item.is_locked,
                )
            )
        db.commit()
        db.refresh(formula)
    except FormulaWeightError:
        raise
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return to_response(formula, total)


def get_formula(db: Session, formula_id: str) -> FormulaResponse | None:
    try:
        formula = db.get(Formula, formula_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if formula is None:
        return None
    return to_response(
        formula, total_weight([(i.phase, i) for i in formula.ingredients])
    )


def list_formulas(db: Session, limit: int = 50) -> list[FormulaResponse]:
    try:
        rows = (
            db.query(Formula).order_by(Formula.updated_at.desc()).limit(limit).all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [
        to_response(f, total_weight([(i.phase, i) for i in f.ingredients]))
        for f in rows
    ]


def update_formula(
    db: Session, formula_id: str, body: FormulaUpdate
) -> FormulaResponse | None:
    items = body.phases.flattened()
    total = check_total(items)
    try:
        formula = db.get(Formula, formula_id)
        if formula is None:
            return None
        latest = (
            db.query(FormulaVersion)
            .filter(FormulaVersion.formula_id == formula_id)
            .order_by(FormulaVersion.version.desc())
            .first()
        )
        db.add(
            FormulaVersion(
                formula_id=formula_id,
                version=(latest.version + 1) if latest else 1,
                snapshot={
                    "name": formula.name,
                    "category": formula.category,
                    "batch_size_g": formula.batch_size_g,
                    "notes": formula.notes,
                    "ingredients": [
                        {
                            "phase": i.phase,
                            "inci": i.inci,
                            "name": i.name,
                            "smiles": i.smiles,
                            "weight_pct": i.weight_pct,
                            "is_locked": i.is_locked,
                        }
                        for i in formula.ingredients
                    ],
                },
            )
        )
        formula.name = body.name
        formula.category = body.category
        formula.batch_size_g = body.batch_size_g
        formula.notes = body.notes
        formula.project_id = body.project_id
        for old in list(formula.ingredients):
            db.delete(old)
        for phase, item in items:
            db.add(
                FormulaIngredient(
                    formula_id=formula_id,
                    phase=phase,
                    inci=item.inci,
                    name=item.name,
                    smiles=item.smiles,
                    weight_pct=item.weight_pct,
                    is_locked=item.is_locked,
                )
            )
        db.commit()
        db.refresh(formula)
    except FormulaWeightError:
        raise
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return to_response(formula, total)


def delete_formula(db: Session, formula_id: str) -> bool:
    try:
        formula = db.get(Formula, formula_id)
        if formula is None:
            return False
        db.delete(formula)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return True


def list_versions(db: Session, formula_id: str) -> list[FormulaVersionOutput] | None:
    try:
        formula = db.get(Formula, formula_id)
        if formula is None:
            return None
        rows = (
            db.query(FormulaVersion)
            .filter(FormulaVersion.formula_id == formula_id)
            .order_by(FormulaVersion.version.desc())
            .all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [
        FormulaVersionOutput(
            version=r.version, snapshot=r.snapshot, created_at=r.created_at
        )
        for r in rows
    ]
