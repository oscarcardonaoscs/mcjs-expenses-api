
from datetime import date
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db


router = APIRouter(
    prefix="/history",
    tags=["History"],
)


def enum_value(value):
    """Return the Enum value, or the original value if already a string."""
    if isinstance(value, Enum):
        return value.value
    return value


@router.get(
    "/service-history",
    response_model=schemas.ServiceHistoryResponse,
)
def get_service_history(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    client_id: Optional[int] = Query(None, ge=1),
    service_type: Optional[schemas.ServiceType] = Query(None),
    payment_status: Optional[
        schemas.ClientPaymentStatus
    ] = Query(None),
    payment_method: Optional[
        schemas.ClientPaymentMethod
    ] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise HTTPException(
            status_code=400,
            detail="date_from cannot be greater than date_to",
        )

    return crud.get_service_history(
        db=db,
        date_from=date_from,
        date_to=date_to,
        client_id=client_id,
        service_type=enum_value(service_type),
        payment_status=enum_value(payment_status),
        payment_method=enum_value(payment_method),
        skip=skip,
        limit=limit,
    )
