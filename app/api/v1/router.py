from fastapi import APIRouter
from .expenses import router as expenses_router
from .categories import router as categories_router
from .vendors import router as vendors_router
from .payment_accounts import router as payments_router
from .reports import router as reports_router

api = APIRouter()
api.include_router(expenses_router)
api.include_router(categories_router)
api.include_router(vendors_router)
api.include_router(payments_router)
api.include_router(reports_router)
