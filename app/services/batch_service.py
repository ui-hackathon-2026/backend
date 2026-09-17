"""Master batch sheet math and SOP template.

Gram conversion is exact deterministic math. SHAP attribution and PDF
rendering arrive with the ML and document layers.
"""

from datetime import datetime

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
        shap_contributions=[],
        sop_steps=sop_steps(body.batch_size_grams),
        created_at=record.created_at,
    )
