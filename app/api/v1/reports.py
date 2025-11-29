from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ... import crud, schemas

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/annual-expenses-by-category",
    response_model=schemas.AnnualExpensesByCategoryResponse,
)
def get_annual_expenses_by_category(
    year: int = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    """
    Return monthly stacked totals by category for a given year.
    Defaults to current year if not provided.
    """
    if year is None:
        year = date.today().year
    return crud.report_annual_expenses_by_category(db, year)
