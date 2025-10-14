from pydantic import BaseModel, Field, constr
from datetime import date, datetime
from typing import Optional, List, Literal

PaymentMethod = Literal["CASH", "CARD", "ZELLE",
                        "VENMO", "CASHAPP", "CHECK"]


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
    category_id: Optional[int] = None
    vendor_id: Optional[int] = None

    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    gallons_miles: Optional[float] = None

    expense_type: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    receipt_url: Optional[str] = None

    total: float
    notes: Optional[str] = None


class ExpenseOut(BaseModel):
    id: int
    date: date

    category_id: Optional[int] = None
    vendor_id: Optional[int] = None

    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    gallons_miles: Optional[float] = None

    expense_type: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_url: Optional[str] = None

    total: float
    notes: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    items: List[ExpenseOut]
