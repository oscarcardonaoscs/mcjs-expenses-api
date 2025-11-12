from pydantic import BaseModel, Field, constr, condecimal
from datetime import date, datetime
from typing import Optional, List
from typing_extensions import Literal

DecimalMoney = condecimal(max_digits=10, decimal_places=3)
DecimalQty = condecimal(max_digits=10, decimal_places=3)

PaymentMethod = Literal["CASH", "CARD", "ZELLE", "VENMO", "CASHAPP", "CHECK"]

PaymentAccountType = Literal["CASH", "DEBIT",
                             "CREDIT", "BANK", "ZELLE", "CHECK", "OTHER"]


# ---------- Category ----------
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryCreate(CategoryBase):
    pass


class CategoryIn(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class CategoryOut(CategoryBase):
    id: int

    class Config:
        from_attributes = True


class CategoriesListResponse(BaseModel):
    items: List[CategoryOut]


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
    items: List[VendorOut]


# ---------- Payment Accounts ----------
class PaymentAccountIn(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    type: PaymentAccountType
    provider: Optional[constr(strip_whitespace=True, max_length=60)] = None
    last4: Optional[constr(strip_whitespace=True,
                           min_length=4, max_length=4)] = None
    is_active: bool = True


class PaymentAccountUpdate(BaseModel):
    name: Optional[constr(strip_whitespace=True,
                          min_length=1, max_length=100)] = None
    type: Optional[PaymentAccountType] = None
    provider: Optional[constr(strip_whitespace=True, max_length=60)] = None
    last4: Optional[constr(strip_whitespace=True,
                           min_length=4, max_length=4)] = None
    is_active: Optional[bool] = None


class PaymentAccountOut(BaseModel):
    id: int
    name: str
    type: str
    provider: Optional[str] = None
    last4: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListPaymentAccountsResponse(BaseModel):
    items: List[PaymentAccountOut]


# ---------- Expense ----------
class ExpenseCreate(BaseModel):
    date: date
    category_id: Optional[int] = None
    vendor_id: Optional[int] = None

    description: Optional[str] = None

    # Helpers / Payroll
    helper_name: Optional[constr(strip_whitespace=True, max_length=100)] = None
    task_project: Optional[constr(
        strip_whitespace=True, max_length=120)] = None
    paid: Optional[bool] = False

    quantity: Optional[DecimalQty] = None
    unit: Optional[str] = None
    # unit_price es dinero, no cantidad
    unit_price: Optional[DecimalMoney] = None

    apply_tax: Optional[bool] = True
    gallons_miles: Optional[DecimalQty] = None

    expense_type: Optional[str] = None  # p.ej., "Helpers"
    payment_method: Optional[PaymentMethod] = None
    receipt_url: Optional[str] = None

    payment_account_id: Optional[int] = None

    total: Optional[DecimalMoney] = None
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    date: Optional[date] = None
    category_id: Optional[int] = None
    vendor_id: Optional[int] = None

    description: Optional[str] = None

    # Helpers / Payroll
    helper_name: Optional[constr(strip_whitespace=True, max_length=100)] = None
    task_project: Optional[constr(
        strip_whitespace=True, max_length=120)] = None
    paid: Optional[bool] = None

    quantity: Optional[DecimalQty] = None
    unit: Optional[str] = None
    unit_price: Optional[DecimalMoney] = None

    apply_tax: Optional[bool] = None
    gallons_miles: Optional[DecimalQty] = None

    expense_type: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    receipt_url: Optional[str] = None

    payment_account_id: Optional[int] = None

    total: Optional[DecimalMoney] = None
    notes: Optional[str] = None


class ExpenseOut(BaseModel):
    id: int
    date: date

    category_id: Optional[int] = None
    vendor_id: Optional[int] = None

    description: Optional[str] = None

    # Helpers / Payroll
    helper_name: Optional[str] = None
    task_project: Optional[str] = None
    paid: Optional[bool] = None

    quantity: Optional[DecimalQty] = None
    unit: Optional[str] = None
    unit_price: Optional[DecimalMoney] = None

    apply_tax: Optional[bool] = None
    gallons_miles: Optional[DecimalQty] = None

    expense_type: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_url: Optional[str] = None

    payment_account_id: Optional[int] = None
    subtotal: Optional[DecimalMoney] = None
    tax_amount: Optional[DecimalMoney] = None
    total: DecimalMoney
    notes: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    items: List[ExpenseOut]
