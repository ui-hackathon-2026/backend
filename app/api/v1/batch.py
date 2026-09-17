from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep
from app.models.formula import Formula
from app.schemas.batch import BatchGenerateRequest, BatchResponse
from app.services.batch_service import generate_batch, get_batch_record, render_batch_pdf

router = APIRouter(prefix="/batch-sheet", tags=["batch-sheet"])


@router.post("/generate", response_model=BatchResponse, status_code=201)
def generate(body: BatchGenerateRequest, db: SessionDep) -> BatchResponse:
    result = generate_batch(db, body)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.get("/download/{record_id}")
def download(record_id: str, db: SessionDep) -> Response:
    record = get_batch_record(db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch record not found"
        )
    formula = db.get(Formula, record.formula_id)
    pdf = render_batch_pdf(
        formula.name if formula else record.formula_id,
        record,
        record.operator_name,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={record.id}.pdf"},
    )
