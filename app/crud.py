from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models, schemas
import logging

logger = logging.getLogger("uvicorn")

# Categories


def create_category(db: Session, data: schemas.CategoryCreate):
    obj = models.Category(name=data.name.strip())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_categories(db: Session):
    q = select(models.Category).order_by(models.Category.name.asc())
    return db.scalars(q).all()


def get_category(db: Session, category_id: int):
    return db.get(models.Category, category_id)


def update_category(db: Session, category_id: int, data: schemas.CategoryUpdate):
    obj = get_category(db, category_id)
    if not obj:
        raise ValueError("Category not found")
    if data.name is not None:
        obj.name = data.name.strip()
    db.commit()
    db.refresh(obj)
    return obj


def delete_category(db: Session, category_id: int):
    obj = get_category(db, category_id)
    if not obj:
        return
    db.delete(obj)
    db.commit()

# Vendors


def create_vendor(db: Session, data: schemas.VendorIn):
    obj = models.Vendor(name=data.name.strip())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_vendors(db: Session):
    q = select(models.Vendor).order_by(models.Vendor.name.asc())
    return db.scalars(q).all()


def get_vendor(db: Session, vendor_id: int):
    return db.get(models.Vendor, vendor_id)


def update_vendor(db: Session, vendor_id: int, data: schemas.VendorUpdate):
    obj = get_vendor(db, vendor_id)
    if not obj:
        raise ValueError("Vendor not found")
    if data.name is not None:
        obj.name = data.name.strip()
    db.commit()
    db.refresh(obj)
    return obj


def delete_vendor(db: Session, vendor_id: int):
    obj = get_vendor(db, vendor_id)
    if not obj:
        return
    db.delete(obj)
    db.commit()


# Expenses


def create_expense(db: Session, data: schemas.ExpenseIn):
    # 🔎 Log detallado del body que llega (Pydantic model)
    logger.info("[create_expense] Received data: %s", data.model_dump())

    # Crear objeto SQLAlchemy
    obj = models.Expense(
        date=data.date,
        category_id=data.category_id,
        vendor_id=data.vendor_id,
        description=data.description,
        quantity=data.quantity,
        unit=data.unit,
        unit_price=data.unit_price,
        gallons_miles=data.gallons_miles,
        expense_type=data.expense_type,
        payment_method=data.payment_method,
        receipt_url=data.receipt_url,
        total=data.total,
        notes=data.notes,
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    # 🔎 Log posterior al insert
    logger.info(
        "[create_expense] Inserted ID=%s | category=%s | vendor=%s | total=%s | notes=%s",
        obj.id,
        obj.category_id,
        obj.vendor_id,
        obj.total,
        obj.notes,
    )

    return obj


def list_expenses(db: Session):
    q = select(models.Expense).order_by(
        models.Expense.date.desc(), models.Expense.id.desc())
    return db.scalars(q).all()


def update_expense(db: Session, expense_id: int, data: schemas.ExpenseIn):
    obj = db.get(models.Expense, expense_id)
    if not obj:
        raise ValueError("Expense not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj
