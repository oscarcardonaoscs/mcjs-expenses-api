from fastapi import APIRouter
from . import expenses, categories, vendors

api_router = APIRouter()
api_router.include_router(expenses.router)
api_router.include_router(categories.router)
api_router.include_router(vendors.router)
