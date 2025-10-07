from pydantic import BaseModel, Field, constr
from datetime import date
from typing import Optional, List


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryCreate(CategoryBase):
    pass


class CategoryIn(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)


class CategoryOut(CategoryBase):
    id: int

    class Config:
        from_attributes = True


class CategoriesListResponse(BaseModel):
    items: list[CategoryOut]


# ---------- Vendor ----------
class VendorOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class VendorIn(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=150)


class VendorUpdate(BaseModel):
    name: Optional[constr(strip_whitespace=True,
                          min_length=1, max_length=150)] = None


class ListVendorsResponse(BaseModel):
    items: list[VendorOut]


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
    items: List[ExpenseOut]
