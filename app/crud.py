from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models, schemas

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
    expense = models.Expense(**data.dict())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


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
