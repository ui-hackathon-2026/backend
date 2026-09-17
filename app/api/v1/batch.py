from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.schemas.batch import BatchGenerateRequest, BatchResponse
from app.services.batch_service import generate_batch

router = APIRouter(prefix="/batch-sheet", tags=["batch-sheet"])


@router.post("/generate", response_model=BatchResponse, status_code=201)
def generate(body: BatchGenerateRequest, db: SessionDep) -> BatchResponse:
    result = generate_batch(db, body)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result
