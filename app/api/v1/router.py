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


api = APIRouter()


api.include_router(expenses_router)
api.include_router(categories_router)
api.include_router(expense_concepts_router)
api.include_router(vendors_router)
api.include_router(payments_router)
api.include_router(reports_router)

api.include_router(helpers_router)
api.include_router(helper_time_entries_router)
api.include_router(helper_work_events_router)
api.include_router(helper_payroll_periods_router)

api.include_router(clients_router)
