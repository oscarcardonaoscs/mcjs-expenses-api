from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=schemas.ListResponse)
def get_categories(db: Session = Depends(get_db)):
    return {"items": crud.list_categories(db)}


@router.post("", response_model=schemas.CategoryOut)
def post_category(data: schemas.CategoryIn, db: Session = Depends(get_db)):
    return crud.create_category(db, data)
