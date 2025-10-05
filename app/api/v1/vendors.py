from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=schemas.ListResponse)
def get_vendors(db: Session = Depends(get_db)):
    return {"items": crud.list_vendors(db)}


@router.post("", response_model=schemas.VendorOut)
def post_vendor(data: schemas.VendorIn, db: Session = Depends(get_db)):
    return crud.create_vendor(db, data)
