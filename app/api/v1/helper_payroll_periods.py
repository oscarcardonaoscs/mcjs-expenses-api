from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas

from typing import Optional

router = APIRouter(
    prefix="/helper-payroll-periods",
    tags=["Helper Payroll Periods"]
)


@router.get("/", response_model=List[schemas.HelperPayrollPeriodResponse])
def get_helper_payroll_periods(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    helper_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    return crud.get_helper_payroll_periods(
        db=db,
        skip=skip,
        limit=limit,
        helper_id=helper_id,
        status=status_filter,
    )


@router.get(
    "/{payroll_id}",
    response_model=schemas.HelperPayrollPeriodDetailResponse
)
def get_helper_payroll_period(payroll_id: int, db: Session = Depends(get_db)):
    payroll = crud.get_helper_payroll_period(db=db, payroll_id=payroll_id)
    if not payroll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper payroll period not found",
        )
    return payroll


@router.post(
    "/",
    response_model=schemas.HelperPayrollPeriodResponse,
    status_code=status.HTTP_201_CREATED
)
def create_helper_payroll_period(
    payroll_in: schemas.HelperPayrollPeriodCreate,
    db: Session = Depends(get_db),
):
    helper = crud.get_helper(db=db, helper_id=payroll_in.helper_id)
    if not helper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper not found",
        )

    return crud.create_helper_payroll_period(db=db, payroll_in=payroll_in)


@router.put("/{payroll_id}", response_model=schemas.HelperPayrollPeriodResponse)
def update_helper_payroll_period(
    payroll_id: int,
    payroll_in: schemas.HelperPayrollPeriodUpdate,
    db: Session = Depends(get_db),
):
    payroll = crud.update_helper_payroll_period(
        db=db,
        payroll_id=payroll_id,
        payroll_in=payroll_in,
    )
    if not payroll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper payroll period not found",
        )
    return payroll


@router.delete("/{payroll_id}", status_code=status.HTTP_200_OK)
def delete_helper_payroll_period(payroll_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_helper_payroll_period(db=db, payroll_id=payroll_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper payroll period not found",
        )
    return {"message": "Helper payroll period deleted successfully"}


@router.post(
    "/generate",
    response_model=schemas.HelperPayrollPeriodResponse,
    status_code=status.HTTP_201_CREATED
)
def generate_helper_payroll_period(
    payload: schemas.HelperPayrollGenerateRequest,
    db: Session = Depends(get_db),
):
    helper = crud.get_helper(db=db, helper_id=payload.helper_id)
    if not helper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper not found",
        )

    payroll = crud.generate_helper_payroll_period(
        db=db,
        helper_id=payload.helper_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        pay_date=payload.pay_date,
    )

    if not payroll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No unassigned time entries found for the selected helper and date range",
        )

    return payroll


@router.post(
    "/{payroll_id}/mark-paid",
    response_model=schemas.HelperPayrollPeriodResponse
)
def mark_helper_payroll_period_paid(
    payroll_id: int,
    payload: schemas.HelperPayrollMarkPaidRequest,
    db: Session = Depends(get_db),
):
    payroll = crud.mark_helper_payroll_period_paid(
        db=db,
        payroll_id=payroll_id,
        pay_date=payload.pay_date,
    )

    if not payroll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Helper payroll period not found",
        )

    return payroll
