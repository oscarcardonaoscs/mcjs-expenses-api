
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...db import get_db
from ... import crud, schemas


router = APIRouter(prefix="/expenses", tags=["expenses"])


# ==========================================
# GET EXPENSES
# ==========================================

@router.get("", response_model=schemas.ListResponse)
def get_expenses(
    category_id: Optional[int] = Query(None, ge=1),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2100),
    vendor: Optional[str] = Query(None, max_length=150),
    payment: Optional[str] = Query(None, max_length=100),
    type_filter: Optional[str] = Query(
        None,
        alias="type",
        max_length=150,
    ),
    search_item: Optional[str] = Query(
        None,
        max_length=150,
    ),
    db: Session = Depends(get_db),
):
    """
    List expenses with optional filters:

    - Category
    - Year
    - Month (optional for annual searches)
    - Vendor
    - Payment
    - Type
    - Search by Item (expense_concepts.name)

    All filters can be combined.
    """

    items = crud.list_expenses(
        db=db,
        category_id=category_id,
        month=month,
        year=year,
        vendor=vendor,
        payment=payment,
        type_filter=type_filter,
        search_item=search_item,
    )

    return {"items": items}


# ==========================================
# GET SINGLE EXPENSE
# ==========================================

@router.get("/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
):
    expense = crud.get_expense(db, expense_id)

    if not expense:
        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return expense


# ==========================================
# CREATE EXPENSE
# ==========================================

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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ==========================================
# UPDATE EXPENSE
# ==========================================

@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def put_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
):
    try:
        return crud.update_expense(
            db,
            expense_id,
            data,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Expense not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


# ==========================================
# DELETE EXPENSE
# ==========================================

@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_expense(
        db,
        expense_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return {"ok": True}
