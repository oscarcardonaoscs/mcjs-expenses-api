from pydantic import BaseModel
from datetime import date
from typing import Optional, List


class CategoryIn(BaseModel):
    name: str


class CategoryOut(CategoryIn):
    id: int

    class Config:
        orm_mode = True


class VendorIn(BaseModel):
    name: str


class VendorOut(VendorIn):
    id: int

    class Config:
        orm_mode = True


class ExpenseIn(BaseModel):
    date: date
    amount: float
    note: Optional[str] = None
    category_id: Optional[int] = None
    vendor_id: Optional[int] = None


class ExpenseOut(ExpenseIn):
    id: int
    category_name: Optional[str] = None
    vendor_name: Optional[str] = None

    class Config:
        orm_mode = True


class ListResponse(BaseModel):
    items: list
