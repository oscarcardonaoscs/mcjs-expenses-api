from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app import crud, models, schemas


router = APIRouter(
    prefix="/helper-work-events",
    tags=["Helper Work Events"],
)


@router.post(
    "/",
    response_model=schemas.HelperWorkEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_helper_work_event(
    work_event: schemas.HelperWorkEventCreate,
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # 1. Validar Client
    # ---------------------------------------------------------
    client = (
        db.query(models.Client)
        .filter(
            models.Client.id == work_event.client_id
        )
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found",
        )

    # ---------------------------------------------------------
    # 2. Validar Location
    #
    # Debe:
    # - existir
    # - pertenecer al client seleccionado
    # - estar activa
    # ---------------------------------------------------------
    location = (
        db.query(models.ClientLocation)
        .filter(
            models.ClientLocation.id == work_event.location_id,
            models.ClientLocation.client_id == work_event.client_id,
            models.ClientLocation.is_active.is_(True),
        )
        .first()
    )

    if not location:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected location does not belong to the "
                "selected client or is inactive"
            ),
        )

    # ---------------------------------------------------------
    # 3. Validar Helpers
    # ---------------------------------------------------------
    helper_ids = [
        helper.helper_id
        for helper in work_event.helpers
    ]

    existing_helpers = (
        db.query(models.Helper)
        .filter(
            models.Helper.id.in_(helper_ids),
            models.Helper.is_active.is_(True),
        )
        .all()
    )

    existing_helper_ids = {
        helper.id
        for helper in existing_helpers
    }

    missing_helper_ids = [
        helper_id
        for helper_id in helper_ids
        if helper_id not in existing_helper_ids
    ]

    if missing_helper_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Helper(s) not found or inactive: "
                f"{missing_helper_ids}"
            ),
        )

    # ---------------------------------------------------------
    # 4. Crear Work Event
    # ---------------------------------------------------------
    return crud.create_helper_work_event(
        db=db,
        work_event=work_event,
    )


@router.get(
    "/",
    response_model=List[schemas.HelperWorkEventResponse],
)
def get_helper_work_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.HelperWorkEvent)
        .options(
            joinedload(
                models.HelperWorkEvent.time_entries
            )
        )
        .order_by(
            models.HelperWorkEvent.work_date.desc(),
            models.HelperWorkEvent.start_time.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.put(
    "/{work_event_id}",
    response_model=schemas.HelperWorkEventResponse,
)
def update_helper_work_event(
    work_event_id: int,
    work_event: schemas.HelperWorkEventCreate,
    db: Session = Depends(get_db),
):
    try:
        updated_event = crud.update_helper_work_event(
            db=db,
            work_event_id=work_event_id,
            work_event=work_event,
        )

        if not updated_event:
            raise HTTPException(
                status_code=404,
                detail="Work event not found",
            )

        return updated_event

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get(
    "/{work_event_id}",
    response_model=schemas.HelperWorkEventResponse,
)
def get_helper_work_event(
    work_event_id: int,
    db: Session = Depends(get_db),
):
    work_event = (
        db.query(models.HelperWorkEvent)
        .options(
            joinedload(
                models.HelperWorkEvent.time_entries
            )
        )
        .filter(
            models.HelperWorkEvent.id == work_event_id
        )
        .first()
    )

    if not work_event:
        raise HTTPException(
            status_code=404,
            detail="Helper work event not found",
        )

    return work_event
