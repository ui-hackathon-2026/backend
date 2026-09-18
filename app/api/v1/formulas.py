from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import OptionalUserDep, SessionDep
from app.schemas.formula import (
    AdjustmentRequest,
    AdjustmentResponse,
    FormulaCreate,
    FormulaMessageCreate,
    FormulaMessageOutput,
    FormulaResponse,
    FormulaUpdate,
    FormulaVersionOutput,
)
from app.services.formula_service import (
    add_message,
    create_formula,
    delete_formula,
    get_formula,
    list_formulas,
    list_messages,
    list_versions,
    propose_adjustment,
    update_formula,
)

router = APIRouter(prefix="/formulas", tags=["formulas"])


@router.post("", response_model=FormulaResponse, status_code=201)
def create(
    body: FormulaCreate, db: SessionDep, user: OptionalUserDep
) -> FormulaResponse:
    owner_id = user.id if user else None
    return create_formula(db, body, owner_id=owner_id)


@router.get("", response_model=list[FormulaResponse])
def list_all(
    db: SessionDep, user: OptionalUserDep, limit: int = 50
) -> list[FormulaResponse]:
    owner_id = user.id if user else None
    return list_formulas(db, limit=min(limit, 200), owner_id=owner_id)


@router.get("/{formula_id}", response_model=FormulaResponse)
def get_one(
    formula_id: str, db: SessionDep, user: OptionalUserDep
) -> FormulaResponse:
    owner_id = user.id if user else None
    result = get_formula(db, formula_id, owner_id=owner_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.put("/{formula_id}", response_model=FormulaResponse)
def update(
    formula_id: str,
    body: FormulaUpdate,
    db: SessionDep,
    user: OptionalUserDep,
    create_version: bool = True,
) -> FormulaResponse:
    owner_id = user.id if user else None
    result = update_formula(
        db, formula_id, body, owner_id=owner_id, create_version=create_version
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.delete("/{formula_id}", status_code=204)
def delete(
    formula_id: str, db: SessionDep, user: OptionalUserDep
) -> Response:
    owner_id = user.id if user else None
    if not delete_formula(db, formula_id, owner_id=owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return Response(status_code=204)


@router.get("/{formula_id}/versions", response_model=list[FormulaVersionOutput])
def versions(
    formula_id: str, db: SessionDep, user: OptionalUserDep
) -> list[FormulaVersionOutput]:
    owner_id = user.id if user else None
    result = list_versions(db, formula_id, owner_id=owner_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.get("/{formula_id}/messages", response_model=list[FormulaMessageOutput])
def messages(
    formula_id: str, db: SessionDep, user: OptionalUserDep
) -> list[FormulaMessageOutput]:
    owner_id = user.id if user else None
    result = list_messages(db, formula_id, owner_id=owner_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.post("/{formula_id}/messages", response_model=FormulaMessageOutput, status_code=201)
def post_message(
    formula_id: str, body: FormulaMessageCreate, db: SessionDep, user: OptionalUserDep
) -> FormulaMessageOutput:
    owner_id = user.id if user else None
    result = add_message(db, formula_id, body, owner_id=owner_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result


@router.post("/{formula_id}/propose-adjustment", response_model=AdjustmentResponse)
def propose(
    formula_id: str, body: AdjustmentRequest, db: SessionDep, user: OptionalUserDep
) -> AdjustmentResponse:
    owner_id = user.id if user else None
    result = propose_adjustment(db, formula_id, body, owner_id=owner_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Formula not found"
        )
    return result
