from pydantic import BaseModel, Field, constr, condecimal, model_validator
from datetime import date, datetime, time
from typing import Optional, List, Dict
from typing_extensions import Literal
from typing import Optional

DecimalMoney = condecimal(max_digits=10, decimal_places=3)
DecimalQty = condecimal(max_digits=10, decimal_places=3)

PaymentMethod = Literal["CASH", "CARD", "ZELLE", "VENMO", "CASHAPP", "CHECK"]

PaymentAccountType = Literal["CASH", "DEBIT",
                             "CREDIT", "BANK", "ZELLE", "CHECK", "OTHER"]

HelperPayrollStatus = Literal["Open", "Ready", "Paid", "Cancelled"]


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
    unit_price: Optional[DecimalMoney] = None

    apply_tax: Optional[bool] = True
    gallons_miles: Optional[DecimalQty] = None

    expense_type: Optional[str] = None
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

    category_name: Optional[str] = None
    vendor_name: Optional[str] = None
    payment_account_last4: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    items: List[ExpenseOut]


class MonthlyCategoryTotals(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    month_label: str
    categories: Dict[str, DecimalMoney]
    total: DecimalMoney

    class Config:
        from_attributes = True


class AnnualExpensesByCategoryResponse(BaseModel):
    year: int
    items: List[MonthlyCategoryTotals]


# ---------- Helpers ----------
class HelperBase(BaseModel):
    first_name: constr(strip_whitespace=True, min_length=1, max_length=100)
    last_name: Optional[constr(strip_whitespace=True, max_length=100)] = None
    phone: Optional[constr(strip_whitespace=True, max_length=30)] = None
    email: Optional[constr(strip_whitespace=True, max_length=150)] = None
    default_work_rate: DecimalMoney = Field(default=15.000)
    default_travel_rate: DecimalMoney = Field(default=7.250)
    is_active: bool = True
    notes: Optional[str] = None


class HelperCreate(HelperBase):
    pass


class HelperUpdate(BaseModel):
    first_name: Optional[constr(strip_whitespace=True,
                                min_length=1, max_length=100)] = None
    last_name: Optional[constr(strip_whitespace=True, max_length=100)] = None
    phone: Optional[constr(strip_whitespace=True, max_length=30)] = None
    email: Optional[constr(strip_whitespace=True, max_length=150)] = None
    default_work_rate: Optional[DecimalMoney] = None
    default_travel_rate: Optional[DecimalMoney] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class HelperResponse(HelperBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HelpersListResponse(BaseModel):
    items: List[HelperResponse]


# ---------- Helper Time Entries ----------
class HelperTimeEntryBase(BaseModel):
    helper_id: int
    client_id: int
    helper_payroll_period_id: Optional[int] = None
    work_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    work_minutes: Optional[int] = Field(default=None, ge=0)
    travel_minutes: int = Field(default=0, ge=0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is None:
            raise ValueError(
                "end_time is required when start_time is provided")

        if self.end_time is not None and self.start_time is None:
            raise ValueError(
                "start_time is required when end_time is provided")

        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")

        return self


class HelperTimeEntryCreate(HelperTimeEntryBase):
    pass


class HelperTimeEntryUpdate(BaseModel):
    helper_id: Optional[int] = None
    helper_payroll_period_id: Optional[int] = None
    work_date: Optional[date] = None
    client_id: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    work_minutes: Optional[int] = Field(default=None, ge=0)
    travel_minutes: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is None:
            raise ValueError(
                "end_time is required when start_time is provided")

        if self.end_time is not None and self.start_time is None:
            raise ValueError(
                "start_time is required when end_time is provided")

        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")

        return self


class HelperTimeEntryResponse(BaseModel):
    id: int
    helper_id: int
    helper_payroll_period_id: Optional[int] = None
    work_date: date
    client_id: int
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    work_minutes: int
    travel_minutes: int
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HelperTimeEntryPayrollDetailResponse(BaseModel):
    id: int
    helper_id: int
    helper_payroll_period_id: Optional[int] = None
    work_date: date
    client_name: str
    description: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    work_minutes: int
    travel_minutes: int
    work_hours: DecimalMoney
    travel_hours: DecimalMoney
    work_rate: DecimalMoney
    travel_rate: DecimalMoney
    line_total: DecimalMoney
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HelperTimeEntriesListResponse(BaseModel):
    items: List[HelperTimeEntryResponse]


# ---------- Helper Payroll Periods ----------
class HelperPayrollPeriodBase(BaseModel):
    helper_id: int
    period_start: date
    period_end: date
    pay_date: Optional[date] = None
    work_rate: DecimalMoney
    travel_rate: DecimalMoney
    total_work_minutes: int = Field(default=0, ge=0)
    total_travel_minutes: int = Field(default=0, ge=0)
    work_amount: DecimalMoney = Field(default=0.000)
    travel_amount: DecimalMoney = Field(default=0.000)
    total_amount: DecimalMoney = Field(default=0.000)
    status: HelperPayrollStatus = "Open"
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_period_dates(self):
        if self.period_end < self.period_start:
            raise ValueError(
                "period_end must be greater than or equal to period_start")
        return self


class HelperPayrollPeriodCreate(HelperPayrollPeriodBase):
    pass


class HelperPayrollPeriodUpdate(BaseModel):
    helper_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    pay_date: Optional[date] = None
    work_rate: Optional[DecimalMoney] = None
    travel_rate: Optional[DecimalMoney] = None
    total_work_minutes: Optional[int] = Field(default=None, ge=0)
    total_travel_minutes: Optional[int] = Field(default=None, ge=0)
    work_amount: Optional[DecimalMoney] = None
    travel_amount: Optional[DecimalMoney] = None
    total_amount: Optional[DecimalMoney] = None
    status: Optional[HelperPayrollStatus] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_period_dates(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError(
                "period_end must be greater than or equal to period_start")
        return self


class HelperPayrollPeriodResponse(BaseModel):
    id: int
    helper_id: int
    helper_name: Optional[str] = None
    period_start: date
    period_end: date
    pay_date: Optional[date] = None
    work_rate: DecimalMoney
    travel_rate: DecimalMoney
    total_work_minutes: int
    total_travel_minutes: int
    work_amount: DecimalMoney
    travel_amount: DecimalMoney
    total_amount: DecimalMoney
    status: HelperPayrollStatus
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HelperPayrollPeriodDetailResponse(BaseModel):
    id: int
    helper_id: int
    helper_name: Optional[str] = None
    period_start: date
    period_end: date
    pay_date: Optional[date] = None
    work_rate: DecimalMoney
    travel_rate: DecimalMoney
    total_work_minutes: int
    total_travel_minutes: int
    work_amount: DecimalMoney
    travel_amount: DecimalMoney
    total_amount: DecimalMoney
    status: HelperPayrollStatus
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    time_entries: List[HelperTimeEntryPayrollDetailResponse] = []

    class Config:
        from_attributes = True


class HelperPayrollPeriodsListResponse(BaseModel):
    items: List[HelperPayrollPeriodResponse]


class HelperPayrollGenerateRequest(BaseModel):
    helper_id: int
    period_start: date
    period_end: date
    pay_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_period_dates(self):
        if self.period_end < self.period_start:
            raise ValueError(
                "period_end must be greater than or equal to period_start")
        return self


class HelperPayrollMarkPaidRequest(BaseModel):
    pay_date: date


class ClientBase(BaseModel):
    name: str
    is_active: bool = True


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
