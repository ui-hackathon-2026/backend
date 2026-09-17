from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep
from app.schemas.formula import (
    FormulaCreate,
    FormulaResponse,
    FormulaUpdate,
    FormulaVersionOutput,
)
from app.services.formula_service import (
    create_formula,
    delete_formula,
    get_formula,
    list_formulas,
    list_versions,
    update_formula,
)

router = APIRouter(prefix="/formulas", tags=["formulas"])


@router.post("", response_model=FormulaResponse, status_code=201)
def create(body: FormulaCreate, db: SessionDep) -> FormulaResponse:
    return create_formula(db, body)


@router.get("", response_model=list[FormulaResponse])
def list_all(db: SessionDep, limit: int = 50) -> list[FormulaResponse]:
    return list_formulas(db, limit=min(limit, 200))


@router.get("/{formula_id}", response_model=FormulaResponse)
def get_one(formula_id: str, db: SessionDep) -> FormulaResponse:
    result = get_formula(db, formula_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.put("/{formula_id}", response_model=FormulaResponse)
def update(
    formula_id: str, body: FormulaUpdate, db: SessionDep
) -> FormulaResponse:
    result = update_formula(db, formula_id, body)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.delete("/{formula_id}", status_code=204)
def delete(formula_id: str, db: SessionDep) -> Response:
    if not delete_formula(db, formula_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return Response(status_code=204)


@router.get("/{formula_id}/versions", response_model=list[FormulaVersionOutput])
def versions(formula_id: str, db: SessionDep) -> list[FormulaVersionOutput]:
    result = list_versions(db, formula_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result
