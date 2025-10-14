from sqlalchemy import Column, Integer, String, DECIMAL, Date, ForeignKey, DateTime
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


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    category_id = Column(Integer, ForeignKey(
        "categories.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    vendor_id = Column(Integer, ForeignKey(
        "vendors.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)

    description = Column(String(255), nullable=True)
    quantity = Column(DECIMAL(10, 3), nullable=True)
    unit = Column(String(30), nullable=True)
    unit_price = Column(DECIMAL(10, 2), nullable=True)
    # un solo campo para galones o millas
    gallons_miles = Column(DECIMAL(10, 3), nullable=True)

    expense_type = Column(String(100), nullable=True)
    payment_method = Column(String(30), nullable=True)
    receipt_url = Column(String(500), nullable=True)

    # Total y Notes:
    # - Si aplicaste renombres (Opción A), ya existen como total/notes:
    # proviene de amount -> total
    total = Column(DECIMAL(10, 2), nullable=False)
    # proviene de note -> notes (TEXT)
    notes = Column(String(65535), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
