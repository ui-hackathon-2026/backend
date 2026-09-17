"""Master batch sheet math, SOP template, and PDF rendering.

Gram conversion is exact deterministic math. SHAP attribution arrives
with the ML layer.
"""

from datetime import datetime

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.models.catalog import BatchRecord
from app.models.formula import Formula
from app.schemas.batch import (
    BatchGenerateRequest,
    BatchResponse,
    ScaledIngredient,
)


def sop_steps(batch_size_g: float) -> list[str]:
    return [
        f"Panaskan Fase A dan Fase B terpisah hingga 75-80C untuk batch {batch_size_g:g} gram.",
        "Emulsifikasi dengan homogenizer 4.500 RPM selama 8 menit.",
        "Dinginkan ke bawah 40C sebelum memasukkan bahan aktif Fase D.",
    ]


def generate_batch(db: Session, body: BatchGenerateRequest) -> BatchResponse | None:
    try:
        formula = db.get(Formula, body.formula_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
    if formula is None:
        return None
    scaled = [
        ScaledIngredient(
            phase=i.phase,
            inci=i.inci,
            grams=round(i.weight_pct / 100.0 * body.batch_size_grams, 2),
        )
        for i in formula.ingredients
    ]
    count = db.query(BatchRecord).count()
    record_id = f"MBMR-{datetime.now().year}-{count + 1:03d}"
    try:
        record = BatchRecord(
            id=record_id,
            formula_id=formula.id,
            batch_size_g=body.batch_size_grams,
            operator_name=body.operator_name,
            scaled_ingredients=[s.model_dump() for s in scaled],
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        raise DatabaseUnavailableError(str(exc)) from exc
    return BatchResponse(
        batch_record_id=record.id,
        formula_id=formula.id,
        batch_size_grams=body.batch_size_grams,
        operator_name=body.operator_name,
        scaled_ingredients=scaled,
        shap_contributions=explain_batch(db, formula),
        sop_steps=sop_steps(body.batch_size_grams),
        created_at=record.created_at,
    )


ROLE_FEATURES = {
    "emulsifier": "emulsifier_pct",
    "humectant": "humectant_pct",
    "thickener": "thickener_pct",
    "active": "active_pct",
    "preservative": "preservative_pct",
    "solvent": "water_phase_pct",
}


def explain_batch(db: Session, formula: Formula) -> list[dict]:
    from app.ml.shap_explainer import attribute_to_ingredients, explain_stability
    from app.models.ingredient import Ingredient
    from app.schemas.simulation import IngredientInput, SimulationRequest
    from app.services.simulation_service import extract_features

    try:
        catalog = {row.inci: row for row in db.query(Ingredient).all()}
        known = set(catalog)
        ingredients = []
        for item in formula.ingredients:
            row = catalog.get(item.inci)
            role = row.default_role if row else "active"
            ingredients.append(
                IngredientInput(
                    name=item.name or item.inci,
                    inci=item.inci,
                    smiles=item.smiles or "O",
                    weight_pct=item.weight_pct,
                    phase=item.phase,
                    role=role,
                    hlb=row.hlb if row else None,
                )
            )
        request = SimulationRequest(formula_name=formula.name, ingredients=ingredients)
        features = extract_features(db, request, known_incis=known)
        buckets: dict[str, list[tuple[str, float]]] = {}
        for item in formula.ingredients:
            row = catalog.get(item.inci)
            role = row.default_role if row else "active"
            if item.phase == "A":
                bucket = "oil_phase_pct"
            else:
                bucket = ROLE_FEATURES.get(role, "active_pct")
            buckets.setdefault(bucket, []).append((item.inci, item.weight_pct))
        return attribute_to_ingredients(explain_stability(features), buckets)
    except Exception:
        return []


def get_batch_record(db: Session, record_id: str) -> BatchRecord | None:
    try:
        return db.get(BatchRecord, record_id)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


def render_batch_pdf(
    formula_name: str,
    record: BatchRecord,
    operator_name: str | None,
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Master Batch Manufacturing Record", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Record: {record.id}    Formula: {formula_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 7,
        f"Batch: {record.batch_size_g:g} g    Operator: {operator_name or '-'}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Weighing Sheet", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    widths = (16, 92, 36, 36)
    for header, width in zip(("Phase", "INCI", "Grams", "Checked"), widths):
        pdf.cell(width, 7, header, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for item in record.scaled_ingredients:
        pdf.cell(widths[0], 7, str(item.get("phase", "")), border=1)
        pdf.cell(widths[1], 7, str(item.get("inci", ""))[:48], border=1)
        pdf.cell(widths[2], 7, f"{item.get('grams', 0):g}", border=1)
        pdf.cell(widths[3], 7, "[ ]", border=1)
        pdf.ln()
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Manufacturing SOP", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for number, step in enumerate(sop_steps(record.batch_size_g), start=1):
        pdf.multi_cell(0, 6, f"{number}. {step}", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
