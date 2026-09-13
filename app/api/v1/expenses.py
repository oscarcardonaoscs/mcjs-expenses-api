from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db import get_db
from ... import crud, schemas


router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=schemas.ListResponse)
def get_expenses(
    category_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List expenses with optional category, month, and year filters."""
    items = crud.list_expenses(
        db,
        category_id=category_id,
        month=month,
        year=year,
    )
    return {"items": items}


@router.get("/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = crud.get_expense(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.post(
    "",
    response_model=schemas.ExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
def post_expense(
    data: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_expense(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def put_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
):
    try:
        return crud.update_expense(db, expense_id, data)
    except ValueError as exc:
        status_code = (
            404 if str(exc) == "Expense not found" else 400
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_expense(db, expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}
