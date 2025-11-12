# app/models.py (fragmento)
from sqlalchemy import (
    Column, Integer, String, DECIMAL, Date, ForeignKey,
    DateTime, Enum, Boolean, Text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    # relación inversa
    expenses = relationship("Expense", back_populates="category")


class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    # relación inversa
    expenses = relationship("Expense", back_populates="vendor")


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum('CASH', 'DEBIT', 'CREDIT', 'BANK', 'ZELLE',
                  'CHECK', 'OTHER', name='payment_account_type'), nullable=False)
    provider = Column(String(60))
    last4 = Column(String(4))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # relación inversa
    expenses = relationship("Expense", back_populates="payment_account")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    category_id = Column(Integer,
                         ForeignKey("categories.id",
                                    ondelete="SET NULL", onupdate="CASCADE"),
                         nullable=True
                         )
    vendor_id = Column(Integer,
                       ForeignKey("vendors.id", ondelete="SET NULL",
                                  onupdate="CASCADE"),
                       nullable=True
                       )

    description = Column(String(255), nullable=True)

    # NUEVOS (ya existen en BD)
    helper_name = Column(String(100), nullable=True)
    task_project = Column(String(120), nullable=True)

    quantity = Column(DECIMAL(10, 3), nullable=True)
    unit = Column(String(30), nullable=True)
    unit_price = Column(DECIMAL(10, 3), nullable=True)

    apply_tax = Column(Boolean, nullable=False, default=True)
    tax_amount = Column(DECIMAL(10, 2), nullable=True)
    subtotal = Column(DECIMAL(10, 2), nullable=True)

    gallons_miles = Column(DECIMAL(10, 3), nullable=True)

    expense_type = Column(String(100), nullable=True)  # e.g., 'Helpers'
    payment_method = Column(String(30), nullable=True)
    receipt_url = Column(String(500), nullable=True)

    payment_account_id = Column(Integer,
                                ForeignKey(
                                    'payment_accounts.id', ondelete="SET NULL", onupdate="CASCADE"),
                                nullable=True, index=True
                                )

    # NUEVO (ya existe en BD)
    paid = Column(Boolean, nullable=False, default=False)

    total = Column(DECIMAL(10, 2), nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
    payment_account = relationship("PaymentAccount", back_populates="expenses")
