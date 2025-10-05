from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=schemas.ListResponse)
def get_expenses(db: Session = Depends(get_db)):
    return {"items": crud.list_expenses(db)}


@router.post("", response_model=schemas.ExpenseOut)
def post_expense(data: schemas.ExpenseIn, db: Session = Depends(get_db)):
    return crud.create_expense(db, data)
