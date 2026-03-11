from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas
from typing import Optional

router = APIRouter(prefix="/helpers", tags=["Helpers"])


@router.get("/", response_model=List[schemas.HelperResponse])
def get_helpers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    return crud.get_helpers(db=db, skip=skip, limit=limit, is_active=is_active)


@router.get("/{helper_id}", response_model=schemas.HelperResponse)
def get_helper(helper_id: int, db: Session = Depends(get_db)):
    helper = crud.get_helper(db=db, helper_id=helper_id)
    if not helper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper not found",
        )
    return helper


@router.post("/", response_model=schemas.HelperResponse, status_code=status.HTTP_201_CREATED)
def create_helper(helper_in: schemas.HelperCreate, db: Session = Depends(get_db)):
    return crud.create_helper(db=db, helper_in=helper_in)


@router.put("/{helper_id}", response_model=schemas.HelperResponse)
def update_helper(
    helper_id: int,
    helper_in: schemas.HelperUpdate,
    db: Session = Depends(get_db),
):
    helper = crud.update_helper(
        db=db, helper_id=helper_id, helper_in=helper_in)
    if not helper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper not found",
        )
    return helper


@router.delete("/{helper_id}", status_code=status.HTTP_200_OK)
def delete_helper(helper_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_helper(db=db, helper_id=helper_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper not found",
        )
    return {"message": "Helper deleted successfully"}
