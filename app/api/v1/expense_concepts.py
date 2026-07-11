from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db


router = APIRouter(
    prefix="/expense-concepts",
    tags=["Expense Concepts"],
)


@router.get(
    "/",
    response_model=schemas.ExpenseConceptsListResponse,
)
def list_expense_concepts(
    category_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=True),
    db: Session = Depends(get_db),
):
    items = crud.list_expense_concepts(
        db=db,
        category_id=category_id,
        is_active=is_active,
    )

    return {"items": items}


@router.get(
    "/{expense_concept_id}",
    response_model=schemas.ExpenseConceptOut,
)
def get_expense_concept(
    expense_concept_id: int,
    db: Session = Depends(get_db),
):
    obj = crud.get_expense_concept(
        db=db,
        expense_concept_id=expense_concept_id,
    )

    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense concept not found",
        )

    return obj


@router.post(
    "/",
    response_model=schemas.ExpenseConceptOut,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_concept(
    data: schemas.ExpenseConceptCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_expense_concept(db=db, data=data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.put(
    "/{expense_concept_id}",
    response_model=schemas.ExpenseConceptOut,
)
@router.patch(
    "/{expense_concept_id}",
    response_model=schemas.ExpenseConceptOut,
)
def update_expense_concept(
    expense_concept_id: int,
    data: schemas.ExpenseConceptUpdate,
    db: Session = Depends(get_db),
):
    try:
        obj = crud.update_expense_concept(
            db=db,
            expense_concept_id=expense_concept_id,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense concept not found",
        )

    return obj


@router.delete(
    "/{expense_concept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_expense_concept(
    expense_concept_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_expense_concept(
        db=db,
        expense_concept_id=expense_concept_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense concept not found",
        )

    return None
