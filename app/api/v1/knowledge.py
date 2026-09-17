from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.models.catalog import Supplier
from app.schemas.knowledge import (
    ConformerRequest,
    FtoRequest,
    SimilarityRequest,
    SimilarityResponse,
    SupplierResponse,
)
from app.services.molecules_service import ConformerError, conformer
from app.services.similarity_service import check_similarity

router = APIRouter(tags=["knowledge"])


@router.post("/similarity/check", response_model=SimilarityResponse)
def similarity(body: SimilarityRequest, db: SessionDep) -> SimilarityResponse:
    return check_similarity(db, body)


@router.post("/patents/fto-check", status_code=503)
def fto_check(body: FtoRequest, db: SessionDep):
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="patent engine not connected",
    )


@router.post("/molecules/conformer-3d", status_code=200)
def conformer_3d(body: ConformerRequest, db: SessionDep):
    try:
        return conformer(body.smiles, body.name)
    except ConformerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.get("/suppliers", response_model=list[SupplierResponse])
def suppliers(db: SessionDep, inci: str | None = None) -> list[SupplierResponse]:
    query = db.query(Supplier)
    if inci:
        query = query.filter(Supplier.ingredient_inci == inci)
    return query.order_by(Supplier.id).limit(200).all()
