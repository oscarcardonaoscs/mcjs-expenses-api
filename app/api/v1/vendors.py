# app/api/v1/vendors.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=schemas.ListVendorsResponse)
def get_vendors(db: Session = Depends(get_db)):
    return {"items": crud.list_vendors(db)}


@router.post("", response_model=schemas.VendorOut)
def post_vendor(data: schemas.VendorIn, db: Session = Depends(get_db)):
    return crud.create_vendor(db, data)


@router.get("/{vendor_id}", response_model=schemas.VendorOut)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    obj = crud.get_vendor(db, vendor_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return obj


@router.put("/{vendor_id}", response_model=schemas.VendorOut)
def put_vendor(vendor_id: int, data: schemas.VendorUpdate, db: Session = Depends(get_db)):
    try:
        return crud.update_vendor(db, vendor_id, data)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vendor not found")


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    obj = crud.get_vendor(db, vendor_id)
    if not obj:
        return  # idempotente
    crud.delete_vendor(db, vendor_id)
