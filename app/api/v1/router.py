from fastapi import APIRouter
from .expenses import router as expenses_router
from .categories import router as categories_router
from .vendors import router as vendors_router

api = APIRouter()
api.include_router(expenses_router)
api.include_router(categories_router)
api.include_router(vendors_router)
