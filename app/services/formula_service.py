"""Formula CRUD with mass-balance validation and version snapshots.

Every update stores the previous ingredient set as a version before
replacing it, the version log is append-only.
"""

import secrets

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, FormulaWeightError
from app.core.llm import get_groq_gateway
from app.models.formula import Formula, FormulaIngredient, FormulaVersion
from app.models.ingredient import Ingredient
from app.schemas.formula import (
    AdjustmentChange,
    AdjustmentRequest,
    AdjustmentResponse,
    FormulaCreate,
    FormulaMessageCreate,
    FormulaMessageOutput,
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
    if len(items) == 0:
        return 0.0
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
        status="EMPTY_DRAFT" if len(formula.ingredients) == 0 else VALID_BALANCED,
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


def create_formula(db: Session, body: FormulaCreate, owner_id: int | None = None) -> FormulaResponse:
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
            owner_id=owner_id,
        )
        db.add(formula)
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
        for phase, item in items:
            known = catalog.get(item.inci)
            db.add(
                FormulaIngredient(
                    formula_id=formula.id,
                    phase=phase,
                    inci=item.inci,
                    name=item.name,
                    smiles=item.smiles,
                    weight_pct=item.weight_pct,
                    is_locked=item.is_locked,
                    cost_idr_per_kg=known.cost_per_kg_idr if known else None,
                    tkdn_pct=known.tkdn_pct if known else None,
                    cost_source="catalog_estimate" if known else "unknown",
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


def get_formula(db: Session, formula_id: str, owner_id: int | None = None) -> FormulaResponse | None:
    try:
        formula = db.query(Formula).filter(Formula.id == formula_id).first()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if formula is None:
        return None
    return to_response(
        formula, total_weight([(i.phase, i) for i in formula.ingredients])
    )


def list_formulas(db: Session, limit: int = 50, owner_id: int | None = None) -> list[FormulaResponse]:
    try:
        query = db.query(Formula)
        if owner_id is not None:
            query = query.filter((Formula.owner_id == owner_id) | (Formula.owner_id.is_(None)))
        rows = query.order_by(Formula.updated_at.desc()).limit(limit).all()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [
        to_response(f, total_weight([(i.phase, i) for i in f.ingredients]))
        for f in rows
    ]


def update_formula(
    db: Session,
    formula_id: str,
    body: FormulaUpdate,
    owner_id: int | None = None,
    create_version: bool = True,
) -> FormulaResponse | None:
    items = body.phases.flattened()
    total = check_total(items)
    try:
        query = db.query(Formula).filter(Formula.id == formula_id)
        if owner_id is not None:
            query = query.filter(Formula.owner_id == owner_id)
        else:
            query = query.filter(Formula.owner_id.is_(None))
        formula = query.first()
        if formula is None:
            return None
        if create_version:
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
        if owner_id is not None and formula.owner_id is None:
            formula.owner_id = owner_id
        for old in list(formula.ingredients):
            db.delete(old)
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
        for phase, item in items:
            known = catalog.get(item.inci)
            db.add(
                FormulaIngredient(
                    formula_id=formula_id,
                    phase=phase,
                    inci=item.inci,
                    name=item.name,
                    smiles=item.smiles,
                    weight_pct=item.weight_pct,
                    is_locked=item.is_locked,
                    cost_idr_per_kg=known.cost_per_kg_idr if known else None,
                    tkdn_pct=known.tkdn_pct if known else None,
                    cost_source="catalog_estimate" if known else "unknown",
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


def delete_formula(db: Session, formula_id: str, owner_id: int | None = None) -> bool:
    try:
        query = db.query(Formula).filter(Formula.id == formula_id)
        if owner_id is not None:
            query = query.filter(Formula.owner_id == owner_id)
        else:
            query = query.filter(Formula.owner_id.is_(None))
        formula = query.first()
        if formula is None:
            return False
        db.delete(formula)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return True


def list_versions(db: Session, formula_id: str, owner_id: int | None = None) -> list[FormulaVersionOutput] | None:
    try:
        formula = db.query(Formula).filter(Formula.id == formula_id).first()
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

ADJUST_SYSTEM = (
    "You reformulate a cosmetic formula from a user request. Given the "
    "current ingredients and the request, respond with JSON keys: title "
    "(string), explanation (string, Bahasa Indonesia), changes (array of "
    "{ingredient_id, name, inci, old_pct, new_pct, phase, action}), "
    "updated_phases (object with phase_a, phase_b, phase_c, phase_d arrays "
    "of {inci, name, weight_pct, is_locked}). Keep total weight at 100. "
    "Return valid JSON only."
)


def ensure_formula_session(db: Session, formula_id: str) -> str:
    from app.models.chat import ChatSession
    from app.models.formula_message import FormulaMessage

    try:
        existing = (
            db.query(FormulaMessage)
            .filter(FormulaMessage.formula_id == formula_id)
            .order_by(FormulaMessage.id.desc())
            .first()
        )
        if existing is not None and existing.session_id:
            return existing.session_id
        session = ChatSession(id=f"sess_{secrets.token_hex(6)}")
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc


def list_messages(
    db: Session, formula_id: str, owner_id: int | None = None
) -> list[FormulaMessageOutput] | None:
    from app.models.formula_message import FormulaMessage

    try:
        formula = db.query(Formula).filter(Formula.id == formula_id).first()
        if formula is None:
            return None
        rows = (
            db.query(FormulaMessage)
            .filter(FormulaMessage.formula_id == formula_id)
            .order_by(FormulaMessage.id)
            .all()
        )
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    return [to_message_output(r) for r in rows]


def to_message_output(row) -> FormulaMessageOutput:
    return FormulaMessageOutput(
        id=row.id,
        session_id=row.session_id or "",
        role=row.role,
        content=row.content,
        proposal=row.proposal,
        linked_artifact_id=row.linked_artifact_id,
        created_at=row.created_at,
    )


def add_message(
    db: Session,
    formula_id: str,
    body: FormulaMessageCreate,
    owner_id: int | None = None,
) -> FormulaMessageOutput | None:
    from app.models.formula_message import FormulaMessage

    try:
        query = db.query(Formula).filter(Formula.id == formula_id)
        if owner_id is not None:
            query = query.filter(Formula.owner_id == owner_id)
        else:
            query = query.filter(Formula.owner_id.is_(None))
        formula = query.first()
        if formula is None:
            formula = Formula(
                id=formula_id,
                name=formula_id.replace("-", " ").title(),
                owner_id=owner_id,
            )
            db.add(formula)
            db.commit()
            db.refresh(formula)
        session_id = ensure_formula_session(db, formula_id)
        from app.models.chat import ChatMessage as ChatRow

        db.add(
            ChatRow(session_id=session_id, role=body.role, content=body.content)
        )
        row = FormulaMessage(
            formula_id=formula_id,
            session_id=session_id,
            role=body.role,
            content=body.content,
            proposal=body.proposal,
            linked_artifact_id=body.linked_artifact_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return to_message_output(row)


def propose_adjustment(
    db: Session,
    formula_id: str,
    body: AdjustmentRequest,
    owner_id: int | None = None,
    gateway=None,
) -> AdjustmentResponse | None:
    import json as jsonlib

    from app.core.config import settings

    try:
        query = db.query(Formula).filter(Formula.id == formula_id)
        if owner_id is not None:
            query = query.filter(Formula.owner_id == owner_id)
        else:
            query = query.filter(Formula.owner_id.is_(None))
        formula = query.first()
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if formula is None:
        return None
    current = [
        {"inci": i.inci, "name": i.name, "weight_pct": i.weight_pct, "phase": i.phase}
        for i in formula.ingredients
    ]
    active = gateway or get_groq_gateway()
    parsed = active.chat_json(
        [
            {
                "role": "user",
                "content": f"{ADJUST_SYSTEM}\nCurrent: {jsonlib.dumps(current)}\nRequest: {body.prompt}",
            }
        ],
        model=settings.groq_model_fast,
        max_tokens=1024,
    )
    phases = parsed.get("updated_phases", {})
    phase_lists = {}
    for key in ("phase_a", "phase_b", "phase_c", "phase_d"):
        cleaned = []
        for item in phases.get(key, []) or []:
            try:
                pct = float(item.get("weight_pct", 0))
            except (TypeError, ValueError):
                continue
            if pct <= 0:
                continue
            cleaned.append(
                {
                    "inci": str(item.get("inci", "")),
                    "name": item.get("name"),
                    "weight_pct": pct,
                    "is_locked": bool(item.get("is_locked", False)),
                }
            )
        phase_lists[key] = cleaned
    total = round(
        sum(float(i.get("weight_pct", 0)) for items in phase_lists.values() for i in items), 2
    )
    old_by_inci = {i["inci"].lower(): i["weight_pct"] for i in current}
    changes = []
    for item in parsed.get("changes", []):
        old_pct = old_by_inci.get(str(item.get("inci", "")).lower())
        try:
            new_pct = float(item.get("new_pct", 0))
        except (TypeError, ValueError):
            new_pct = 0.0
        raw_iid = item.get("ingredient_id")
        raw_inci = item.get("inci")
        changes.append(
            AdjustmentChange(
                ingredient_id=str(raw_iid) if raw_iid is not None else None,
                name=str(item.get("name") or raw_inci or "ingredient"),
                inci=str(raw_inci) if raw_inci is not None else None,
                old_pct=old_pct,
                new_pct=new_pct,
                phase=str(item.get("phase") or "B"),
                action=str(item.get("action") or "modified"),
            )
        )
    return AdjustmentResponse(
        formula_id=formula_id,
        title=parsed.get("title", "Formula adjustment"),
        explanation=parsed.get("explanation", ""),
        changes=changes,
        updated_phases=phase_lists,
        total_weight_pct=total,
    )
