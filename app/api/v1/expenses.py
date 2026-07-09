from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
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
    """
    Lista de gastos con filtros opcionales:
    - category_id: id de categoría
    - month: 1-12
    - year: YYYY
    """
    items = crud.list_expenses(
        db,
        category_id=category_id,
        month=month,
        year=year,
    )
    return {"items": items}


@router.post("", response_model=schemas.ExpenseOut)
def post_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_expense(db, data)

@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def put_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
):
    try:
        expense = crud.update_expense(db, expense_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return expense


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_expense(db, expense_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"ok": True}