from sqlalchemy.orm import Session
from . import models, schemas

# Categories


def create_category(db: Session, data: schemas.CategoryIn):
    obj = models.Category(name=data.name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_categories(db: Session):
    return db.query(models.Category).order_by(models.Category.name).all()

# Vendors


def create_vendor(db: Session, data: schemas.VendorIn):
    obj = models.Vendor(name=data.name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_vendors(db: Session):
    return db.query(models.Vendor).order_by(models.Vendor.name).all()

# Expenses


def create_expense(db: Session, data: schemas.ExpenseIn):
    obj = models.Expense(**data.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_expenses(db: Session):
    q = db.query(models.Expense).all()
    # map names for convenience
    out = []
    for e in q:
        out.append({
            "id": e.id, "date": e.date, "amount": float(e.amount),
            "note": e.note,
            "category_id": e.category_id, "vendor_id": e.vendor_id,
            "category_name": e.category.name if e.category else None,
            "vendor_name": e.vendor.name if e.vendor else None
        })
    return out
