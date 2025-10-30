# app/routers/payment_accounts.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/payment-accounts", tags=["Payment Accounts"])


@router.get("", response_model=schemas.ListPaymentAccountsResponse)
def list_all(
    db: Session = Depends(get_db),
    types: Optional[str] = Query(
        default=None, description="CSV de tipos: CASH,DEBIT,CREDIT,BANK,ZELLE,CHECK,OTHER"
    ),
    is_active: Optional[bool] = Query(default=True),
):
    """
    Lista todas las cuentas, con opción de filtrar por tipo(s) y estado activo.
    Ejemplo:
      /payment-accounts?types=DEBIT,CREDIT
    """
    items = crud.list_payment_accounts(db, types=types, is_active=is_active)
    return {"items": items}


@router.post("", response_model=schemas.PaymentAccountOut, status_code=201)
def create(data: schemas.PaymentAccountIn, db: Session = Depends(get_db)):
    return crud.create_payment_account(db, data)


@router.get("/{account_id}", response_model=schemas.PaymentAccountOut)
def get_one(account_id: int, db: Session = Depends(get_db)):
    obj = crud.get_payment_account(db, account_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.put("/{account_id}", response_model=schemas.PaymentAccountOut)
def update(account_id: int, data: schemas.PaymentAccountUpdate, db: Session = Depends(get_db)):
    try:
        return crud.update_payment_account(db, account_id, data)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


@router.delete("/{account_id}", status_code=204)
def remove(account_id: int, db: Session = Depends(get_db)):
    crud.delete_payment_account(db, account_id)
    return None
