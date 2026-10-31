# app/api/v1/financial_dashboard.py
from datetime import date
import calendar
from decimal import Decimal
from typing import Optional, Tuple, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app import models

router = APIRouter(prefix="/dashboard", tags=["Financial Dashboard"])


class FinancialSummaryResponse(BaseModel):
    year: int
    month: int
    income_received: Decimal
    expenses: Decimal
    net_balance: Decimal
    services_completed: int
    expense_ratio: Optional[Decimal]


def month_bounds(year: int, month: int) -> Tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


@router.get("/financial-summary", response_model=FinancialSummaryResponse)
def get_financial_summary(
    year: int = Query(..., ge=2000, le=9998),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    start, end = month_bounds(year, month)

    income_received = db.query(
        func.coalesce(func.sum(models.HelperWorkEvent.service_amount), 0)
    ).filter(
        models.HelperWorkEvent.payment_status == "Collected",
        models.HelperWorkEvent.payment_received_date >= start,
        models.HelperWorkEvent.payment_received_date < end,
    ).scalar()

    expenses = db.query(
        func.coalesce(func.sum(models.Expense.total), 0)
    ).filter(
        models.Expense.date >= start,
        models.Expense.date < end,
    ).scalar()

    services_completed = db.query(
        func.count(models.HelperWorkEvent.id)
    ).filter(
        models.HelperWorkEvent.work_date >= start,
        models.HelperWorkEvent.work_date < end,
        models.HelperWorkEvent.start_time.isnot(None),
        models.HelperWorkEvent.end_time.isnot(None),
    ).scalar()

    income = Decimal(str(income_received or 0)).quantize(Decimal("0.01"))
    expense_total = Decimal(str(expenses or 0)).quantize(Decimal("0.01"))
    balance = income - expense_total
    ratio = (
        (expense_total / income * Decimal("100")).quantize(Decimal("0.01"))
        if income > 0 else None
    )

    return FinancialSummaryResponse(
        year=year,
        month=month,
        income_received=income,
        expenses=expense_total,
        net_balance=balance,
        services_completed=int(services_completed or 0),
        expense_ratio=ratio,
    )


class MonthlyIncomeExpenses(BaseModel):
    month: int
    month_label: str
    income: Decimal
    expenses: Decimal


class IncomeExpensesAnnualResponse(BaseModel):
    year: int
    items: List[MonthlyIncomeExpenses]


@router.get("/income-expenses", response_model=IncomeExpensesAnnualResponse)
def get_income_expenses(
    year: int = Query(..., ge=2000, le=9998),
    db: Session = Depends(get_db),
):
    """Monthly income received vs purchase-date expenses for one year."""
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)

    income_rows = (
        db.query(
            func.month(models.HelperWorkEvent.payment_received_date).label(
                "month"),
            func.sum(models.HelperWorkEvent.service_amount).label("total"),
        )
        .filter(
            models.HelperWorkEvent.payment_status == "Collected",
            models.HelperWorkEvent.payment_received_date >= start,
            models.HelperWorkEvent.payment_received_date < end,
        )
        .group_by(func.month(models.HelperWorkEvent.payment_received_date))
        .all()
    )

    expense_rows = (
        db.query(
            func.month(models.Expense.date).label("month"),
            func.sum(models.Expense.total).label("total"),
        )
        .filter(models.Expense.date >= start, models.Expense.date < end)
        .group_by(func.month(models.Expense.date))
        .all()
    )

    income_by_month = {
        int(month): Decimal(str(total or 0)).quantize(Decimal("0.01"))
        for month, total in income_rows
    }
    expenses_by_month = {
        int(month): Decimal(str(total or 0)).quantize(Decimal("0.01"))
        for month, total in expense_rows
    }

    return IncomeExpensesAnnualResponse(
        year=year,
        items=[
            MonthlyIncomeExpenses(
                month=month,
                month_label=calendar.month_abbr[month],
                income=income_by_month.get(month, Decimal("0.00")),
                expenses=expenses_by_month.get(month, Decimal("0.00")),
            )
            for month in range(1, 13)
        ],
    )


class IncomeByServiceTypeItem(BaseModel):
    service_type: str
    amount: Decimal
    percentage: Decimal


class IncomeByServiceTypeResponse(BaseModel):
    year: int
    month: int
    total_income: Decimal
    items: List[IncomeByServiceTypeItem]


@router.get("/income-by-service-type", response_model=IncomeByServiceTypeResponse)
def get_income_by_service_type(
    year: int = Query(..., ge=2000, le=9998),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Value of completed services by service type and work_date.

    Includes both Collected and Pending events: this is completed-service
    revenue, not necessarily money received during the selected month.
    """
    start, end = month_bounds(year, month)
    event = models.HelperWorkEvent
    service_type = func.coalesce(
        func.nullif(func.trim(event.service_type), ""),
        "Other",
    )
    rows = (
        db.query(
            service_type.label("service_type"),
            func.sum(event.service_amount).label("total"),
        )
        .filter(
            event.work_date >= start,
            event.work_date < end,
            event.start_time.isnot(None),
            event.end_time.isnot(None),
            event.service_amount.isnot(None),
        )
        .group_by(service_type)
        .order_by(func.sum(event.service_amount).desc())
        .all()
    )

    amounts = [
        (name, Decimal(str(total or 0)).quantize(Decimal("0.01")))
        for name, total in rows
    ]
    total_income = sum((amount for _, amount in amounts), Decimal("0.00"))

    items = [
        IncomeByServiceTypeItem(
            service_type=name,
            amount=amount,
            percentage=(
                (amount * Decimal("100") / total_income).quantize(Decimal("0.01"))
                if total_income > 0 else Decimal("0.00")
            ),
        )
        for name, amount in amounts
    ]

    return IncomeByServiceTypeResponse(
        year=year,
        month=month,
        total_income=total_income,
        items=items,
    )
