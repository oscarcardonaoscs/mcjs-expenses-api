from sqlalchemy import (
    Column, Integer, String, DECIMAL, Date, Time, ForeignKey,
    DateTime, Enum, Boolean, Text, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    expenses = relationship("Expense", back_populates="category")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)

    expenses = relationship("Expense", back_populates="vendor")


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(
        Enum('CASH', 'DEBIT', 'CREDIT', 'BANK', 'ZELLE', 'CHECK', 'OTHER',
             name='payment_account_type'),
        nullable=False
    )
    provider = Column(String(60))
    last4 = Column(String(4))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    expenses = relationship("Expense", back_populates="payment_account")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True
    )
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True
    )

    description = Column(String(255), nullable=True)

    helper_name = Column(String(100), nullable=True)
    task_project = Column(String(120), nullable=True)

    quantity = Column(DECIMAL(10, 3), nullable=True)
    unit = Column(String(30), nullable=True)
    unit_price = Column(DECIMAL(10, 3), nullable=True)

    apply_tax = Column(Boolean, nullable=False, default=True)
    tax_amount = Column(DECIMAL(10, 2), nullable=True)
    subtotal = Column(DECIMAL(10, 2), nullable=True)

    gallons_miles = Column(DECIMAL(10, 3), nullable=True)

    expense_type = Column(String(100), nullable=True)
    payment_method = Column(String(30), nullable=True)
    receipt_url = Column(String(500), nullable=True)

    payment_account_id = Column(
        Integer,
        ForeignKey('payment_accounts.id',
                   ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True
    )

    paid = Column(Boolean, nullable=False, default=False)

    total = Column(DECIMAL(10, 2), nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
    payment_account = relationship("PaymentAccount", back_populates="expenses")


class Helper(Base):
    __tablename__ = "helpers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(150), nullable=True)
    default_work_rate = Column(DECIMAL(10, 2), nullable=False, default=15.00)
    default_travel_rate = Column(DECIMAL(10, 2), nullable=False, default=7.25)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    time_entries = relationship(
        "HelperTimeEntry",
        back_populates="helper",
        cascade="all, delete-orphan"
    )

    payroll_periods = relationship(
        "HelperPayrollPeriod",
        back_populates="helper",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_helpers_is_active", "is_active"),
        Index("idx_helpers_name", "first_name", "last_name"),
    )


class HelperPayrollPeriod(Base):
    __tablename__ = "helper_payroll_periods"

    id = Column(Integer, primary_key=True, index=True)
    helper_id = Column(
        Integer,
        ForeignKey("helpers.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=True)

    work_rate = Column(DECIMAL(10, 2), nullable=False)
    travel_rate = Column(DECIMAL(10, 2), nullable=False)

    total_work_minutes = Column(Integer, nullable=False, default=0)
    total_travel_minutes = Column(Integer, nullable=False, default=0)

    work_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    travel_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)

    status = Column(
        Enum('Open', 'Ready', 'Paid', 'Cancelled',
             name='helper_payroll_status'),
        nullable=False,
        default='Open'
    )

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    helper = relationship("Helper", back_populates="payroll_periods")

    @property
    def helper_name(self):
        if not self.helper:
            return None

        parts = [self.helper.first_name, self.helper.last_name]
        return " ".join([p for p in parts if p])

    time_entries = relationship(
        "HelperTimeEntry",
        back_populates="payroll_period",
        passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint(
            "helper_id", "period_start", "period_end",
            name="uk_helper_payroll_period"
        ),
        Index("idx_helper_payroll_periods_period_start", "period_start"),
        Index("idx_helper_payroll_periods_period_end", "period_end"),
        Index("idx_helper_payroll_periods_pay_date", "pay_date"),
        Index("idx_helper_payroll_periods_status", "status"),
    )


class HelperTimeEntry(Base):
    __tablename__ = "helper_time_entries"

    id = Column(Integer, primary_key=True, index=True)
    helper_id = Column(
        Integer,
        ForeignKey("helpers.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True
    )
    helper_payroll_period_id = Column(
        Integer,
        ForeignKey("helper_payroll_periods.id",
                   ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True
    )

    work_date = Column(Date, nullable=False)
    client_name = Column(String(200), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    work_minutes = Column(Integer, nullable=False, default=0)
    travel_minutes = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    helper = relationship("Helper", back_populates="time_entries")
    payroll_period = relationship(
        "HelperPayrollPeriod", back_populates="time_entries")

    __table_args__ = (
        Index("idx_helper_time_entries_work_date", "work_date"),
        Index("idx_helper_time_entries_helper_date", "helper_id", "work_date"),
        Index("idx_helper_time_entries_client_name", "client_name"),
    )
