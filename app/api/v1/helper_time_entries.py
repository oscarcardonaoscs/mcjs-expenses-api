from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas

from typing import Optional

router = APIRouter(prefix="/helper-time-entries", tags=["Helper Time Entries"])


@router.get("/", response_model=List[schemas.HelperTimeEntryResponse])
def get_helper_time_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    helper_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    unassigned_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    return crud.get_helper_time_entries(
        db=db,
        skip=skip,
        limit=limit,
        helper_id=helper_id,
        date_from=date_from,
        date_to=date_to,
        unassigned_only=unassigned_only,
    )


@router.get("/{entry_id}", response_model=schemas.HelperTimeEntryResponse)
def get_helper_time_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = crud.get_helper_time_entry(db=db, entry_id=entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper time entry not found",
        )
    return entry


@router.post(
    "/",
    response_model=schemas.HelperTimeEntryCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_helper_time_entry(
    entry_in: schemas.HelperTimeEntryCreate,
    db: Session = Depends(get_db),
):
    for helper_entry in entry_in.helpers:
        helper = crud.get_helper(db=db, helper_id=helper_entry.helper_id)

        if not helper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Helper not found: {helper_entry.helper_id}",
            )

    try:
        return crud.create_helper_time_entry(db=db, entry_in=entry_in)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.put("/{entry_id}", response_model=schemas.HelperTimeEntryResponse)
def update_helper_time_entry(
    entry_id: int,
    entry_in: schemas.HelperTimeEntryUpdate,
    db: Session = Depends(get_db),
):
    try:
        entry = crud.update_helper_time_entry(
            db=db,
            entry_id=entry_id,
            entry_in=entry_in,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper time entry not found",
        )

    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_200_OK)
def delete_helper_time_entry(entry_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_helper_time_entry(db=db, entry_id=entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper time entry not found",
        )
    return {"message": "Helper time entry deleted successfully"}
