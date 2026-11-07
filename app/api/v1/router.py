
import os

from fastapi import APIRouter

from .expenses import router as expenses_router
from .categories import router as categories_router
from .expense_concepts import router as expense_concepts_router
from .vendors import router as vendors_router
from .payment_accounts import router as payments_router
from .reports import router as reports_router

from .helpers import router as helpers_router
from .helper_time_entries import router as helper_time_entries_router
from .helper_work_events import router as helper_work_events_router
from .helper_payroll_periods import router as helper_payroll_periods_router

from .clients import router as clients_router
from .history import router as history_router

# Financial Dashboard
from .financial_dashboard import router as financial_dashboard_router


api = APIRouter()


# ---------------------------------------------------------
# Expenses
# ---------------------------------------------------------

api.include_router(expenses_router)
api.include_router(categories_router)
api.include_router(expense_concepts_router)
api.include_router(vendors_router)
api.include_router(payments_router)
api.include_router(reports_router)


# ---------------------------------------------------------
# Helpers / Payroll / Work Events
# ---------------------------------------------------------

api.include_router(helpers_router)
api.include_router(helper_time_entries_router)
api.include_router(helper_work_events_router)
api.include_router(helper_payroll_periods_router)


# ---------------------------------------------------------
# Clients / History
# ---------------------------------------------------------

api.include_router(clients_router)
api.include_router(history_router)


# ---------------------------------------------------------
# Financial Dashboard
# ---------------------------------------------------------

api.include_router(financial_dashboard_router)


# Operations - Development Only
# Python 3.10 compatible
# ---------------------------------------------------------

OPERATIONS_ENABLED = (
    os.getenv("MCJ_ENV", "").strip().lower() == "development"
    and os.getenv("OPERATIONS_ENABLED", "false").strip().lower() == "true"
)

if OPERATIONS_ENABLED:
    from .operations.planning import (
        router as operations_planning_router,
    )

    from .operations.calendar import (
        router as operations_calendar_router,
    )
    from .operations.teams import (
        router as operations_teams_router,
    )

    api.include_router(operations_planning_router)
    api.include_router(operations_calendar_router)
    api.include_router(operations_teams_router)
