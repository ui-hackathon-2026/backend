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


def get_formula(db: Session, formula_id: str, owner_id: int | None = None) -> FormulaResponse | None:
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
    return to_response(
        formula, total_weight([(i.phase, i) for i in formula.ingredients])
    )


def list_formulas(db: Session, limit: int = 50, owner_id: int | None = None) -> list[FormulaResponse]:
    try:
        query = db.query(Formula)
        if owner_id is not None:
            # Only return formulas belonging to current user
            query = query.filter(Formula.owner_id == owner_id)
        else:
            # If no authenticated user, only return unowned/public chassis
            query = query.filter(Formula.owner_id.is_(None))
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


def propose_formula_adjustment(
    db: Session,
    formula_id: str,
    prompt: str,
    owner_id: int | None = None,
):
    from app.schemas.formula import (
        FormulaAdjustmentResponse,
        FormulaChangeItem,
        FormulaIngredientInput,
        FormulaPhases,
    )

    query = db.query(Formula).filter(Formula.id == formula_id)
    if owner_id is not None:
        query = query.filter(Formula.owner_id == owner_id)
    else:
        query = query.filter(Formula.owner_id.is_(None))
    formula = query.first()
    if formula is None:
        return None

    if not formula.ingredients:
        return None

    p_lower = prompt.lower()

    # Determine intent & target adjustments
    # Cosmetic heuristic domain rules:
    # 1. 'lembut' / 'halus' / 'soft' / 'smooth': increase emollient (Squalane/Dimethicone/Cetyl Alcohol)
    # 2. 'ringan' / 'light' / 'tidak lengket' / 'non-greasy': decrease heavy emollients, increase lighter solvent/water
    # 3. 'lembab' / 'hydrating' / 'moist' / 'kering': increase humectant (Glycerin/Hyaluronic Acid/Butylene Glycol)
    # 4. 'kental' / 'viskositas' / 'thick': increase thickener (Xanthan Gum / Carbomer / Acrylates)
    # 5. 'encer' / 'cair' / 'flow': decrease thickener
    # 6. 'cogs' / 'hemat' / 'biaya' / 'cost' / 'murah': reduce expensive actives/emollients (Squalane/Niacinamide/Peptides)
    # 7. specific ingredient mentions (squalane, glycerin, niacinamide, aqua, etc.)

    title = "Rekomendasi Penyesuaian Formula Teroptimasi"
    explanation = ""
    target_inci = None
    delta = 0.0

    if "lembut" in p_lower or "halus" in p_lower or "soft" in p_lower or "smooth" in p_lower:
        title = "Peningkatan Tekstur Lembut & Emolliency"
        explanation = (
            "Meningkatkan fraksi emollient untuk memperkaya sensorial skin-feel dan kelembutan aplikasi, "
            "dengan auto-kompensasi massa pada fase pelarut (Aqua) agar total formula presisi 100.0%."
        )
        target_inci = "squalane"
        delta = 1.0
    elif "ringan" in p_lower or "light" in p_lower or "lengket" in p_lower:
        title = "Optimasi Tekstur Ringan & Quick-Absorbing"
        explanation = (
            "Mengurangi konsentrasi lipid emollient untuk sensasi akhir yang lebih cepat meresap dan bebas rasa lengket, "
            "diseimbangkan dengan peningkatan fase air."
        )
        target_inci = "squalane"
        delta = -1.0
    elif "lembab" in p_lower or "kering" in p_lower or "moist" in p_lower or "hydrat" in p_lower:
        title = "Peningkatan Kapasitas Hidrasi & Humektan"
        explanation = (
            "Menaikkan humektan pengikat air (Glycerin) untuk menahan kelembapan stratum corneum lebih lama, "
            "dengan penyesuaian solvent balance 100.0%."
        )
        target_inci = "glycerin"
        delta = 1.5
    elif "kental" in p_lower or "viskositas" in p_lower or "thick" in p_lower:
        title = "Peningkatan Viskositas & Body Sediaan"
        explanation = (
            "Meningkatkan konsentrasi rheology modifier / gelling agent untuk membentuk struktur gel-krim yang lebih kokoh, "
            "dengan kompensasi massa otomatis."
        )
        target_inci = "xanthan"
        delta = 0.3
    elif "encer" in p_lower or "cair" in p_lower:
        title = "Penurunan Viskositas Sediaan (Fluid Texture)"
        explanation = (
            "Mengurangi konsentrasi rheology modifier untuk profil alir yang lebih encer dan mudah diaplikasikan via dropper/pump."
        )
        target_inci = "xanthan"
        delta = -0.2
    elif "hemat" in p_lower or "cogs" in p_lower or "biaya" in p_lower or "cost" in p_lower:
        title = "Optimasi COGS & Efisiensi Biaya Bahan Baku"
        explanation = (
            "Mereduksi bahan baku premium emollient secara terukur untuk memangkas unit cost produksi tanpa mengorbankan stabilitas emulsi."
        )
        target_inci = "squalane"
        delta = -1.0
    else:
        # Generic smart adjustment based on prompt keywords
        title = "Penyesuaian Formula Sesuai Parameter R&D"
        explanation = (
            f"Menganalisis permintaan '{prompt}' dan mengoptimalkan keseimbangan rasio aktif-emollient "
            "serta menjaga kesetimbangan massa 100.0%."
        )
        # Check if user mentioned specific known ingredient
        for ing in formula.ingredients:
            if ing.name and ing.name.lower() in p_lower:
                target_inci = ing.name.lower()
                delta = 0.5
                break
            if ing.inci and ing.inci.lower() in p_lower:
                target_inci = ing.inci.lower()
                delta = 0.5
                break
        if not target_inci:
            target_inci = "squalane"
            delta = 0.5

    # Find candidate ingredient in formula
    chosen_ing = None
    if target_inci:
        for ing in formula.ingredients:
            if target_inci in (ing.name or "").lower() or target_inci in (ing.inci or "").lower():
                chosen_ing = ing
                break

    # If target not present, pick any non-water ingredient
    if chosen_ing is None:
        for ing in formula.ingredients:
            if not ("aqua" in ing.inci.lower() or "water" in (ing.name or "").lower()):
                chosen_ing = ing
                delta = 0.5
                break

    # Find solvent (Aqua / Water)
    solvent_ing = None
    for ing in formula.ingredients:
        if "aqua" in ing.inci.lower() or "water" in (ing.name or "").lower() or ing.phase == "B":
            if "aqua" in ing.inci.lower() or "water" in (ing.name or "").lower():
                solvent_ing = ing
                break
    if solvent_ing is None and formula.ingredients:
        solvent_ing = formula.ingredients[0]

    changes: list[FormulaChangeItem] = []
    updated_items_by_phase: dict[str, list[FormulaIngredientInput]] = {"A": [], "B": [], "C": [], "D": []}

    if chosen_ing and solvent_ing and chosen_ing.id != solvent_ing.id:
        old_target_pct = chosen_ing.weight_pct
        new_target_pct = round(max(0.05, old_target_pct + delta), 2)
        actual_delta = round(new_target_pct - old_target_pct, 2)

        old_solvent_pct = solvent_ing.weight_pct
        new_solvent_pct = round(max(0.1, old_solvent_pct - actual_delta), 2)

        for ing in formula.ingredients:
            curr_pct = ing.weight_pct
            if ing.id == chosen_ing.id:
                curr_pct = new_target_pct
                changes.append(
                    FormulaChangeItem(
                        ingredient_id=str(ing.id),
                        name=ing.name or ing.inci,
                        inci=ing.inci,
                        phase=ing.phase,
                        old_pct=old_target_pct,
                        new_pct=new_target_pct,
                        action="modified",
                    )
                )
            elif ing.id == solvent_ing.id:
                curr_pct = new_solvent_pct
                changes.append(
                    FormulaChangeItem(
                        ingredient_id=str(ing.id),
                        name=ing.name or ing.inci,
                        inci=ing.inci,
                        phase=ing.phase,
                        old_pct=old_solvent_pct,
                        new_pct=new_solvent_pct,
                        action="modified",
                    )
                )

            phase_key = ing.phase if ing.phase in updated_items_by_phase else "B"
            updated_items_by_phase[phase_key].append(
                FormulaIngredientInput(
                    inci=ing.inci,
                    name=ing.name,
                    smiles=ing.smiles,
                    weight_pct=curr_pct,
                    is_locked=ing.is_locked,
                )
            )
    else:
        # No modification possible, return as is
        for ing in formula.ingredients:
            phase_key = ing.phase if ing.phase in updated_items_by_phase else "B"
            updated_items_by_phase[phase_key].append(
                FormulaIngredientInput(
                    inci=ing.inci,
                    name=ing.name,
                    smiles=ing.smiles,
                    weight_pct=ing.weight_pct,
                    is_locked=ing.is_locked,
                )
            )

    updated_phases = FormulaPhases(
        phase_a=updated_items_by_phase["A"],
        phase_b=updated_items_by_phase["B"],
        phase_c=updated_items_by_phase["C"],
        phase_d=updated_items_by_phase["D"],
    )

    tot = round(sum(item.weight_pct for _, item in updated_phases.flattened()), 2)

    return FormulaAdjustmentResponse(
        formula_id=formula.id,
        title=title,
        explanation=explanation,
        changes=changes,
        updated_phases=updated_phases,
        total_weight_pct=tot,
    )


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
        query = db.query(Formula).filter(Formula.id == formula_id)
        if owner_id is not None:
            query = query.filter(Formula.owner_id == owner_id)
        else:
            query = query.filter(Formula.owner_id.is_(None))
        formula = query.first()
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