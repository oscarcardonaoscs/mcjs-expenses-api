from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models, schemas
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger("uvicorn")

TAX_RATE = Decimal("0.09")
M2 = Decimal("0.01")
M3 = Decimal("0.001")


def _money(x: Decimal) -> Decimal:
    return x.quantize(M2, rounding=ROUND_HALF_UP)


def _qty(x: Decimal) -> Decimal:
    return x.quantize(M3, rounding=ROUND_HALF_UP)

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


# ---------- Expenses ----------


def _compute_from_parts(unit_price, quantity, apply_tax_bool: bool):
    """
    Devuelve (subtotal, tax, total) usando Decimal y redondeo financiero.
    """
    up = Decimal(str(unit_price))
    qty = Decimal(str(quantity))
    sub = _money(up * qty)
    tax = _money(sub * TAX_RATE) if apply_tax_bool else Decimal("0.00")
    tot = _money(sub + tax)
    return sub, tax, tot


def create_expense(db: Session, data: schemas.ExpenseCreate):
    logger.info("[create_expense] Received data: %s", data.model_dump())

    apply_tax_bool = True if data.apply_tax is None else data.apply_tax

    # Normaliza strings
    desc = data.description.strip() if data.description else None
    unit = data.unit.strip() if data.unit else None
    exp_type = data.expense_type.strip() if data.expense_type else None
    receipt = data.receipt_url.strip() if data.receipt_url else None
    notes = data.notes.strip() if data.notes else None

    subtotal = None
    tax_amount = Decimal("0.00")
    total = None

    # Caso A: se proporcionan unit_price y quantity -> calcular
    if data.unit_price is not None and data.quantity is not None:
        subtotal, tax_amount, total = _compute_from_parts(
            unit_price=data.unit_price,
            quantity=data.quantity,
            apply_tax_bool=apply_tax_bool
        )
        quantity = _qty(Decimal(str(data.quantity)))
        unit_price = _money(Decimal(str(data.unit_price)))
    else:
        # Caso B: no hay partes -> usar total manual
        if data.total is None:
            raise ValueError(
                "Either (unit_price & quantity) or total must be provided.")
        total = _money(Decimal(str(data.total)))
        quantity = Decimal(str(data.quantity)
                           ) if data.quantity is not None else None
        unit_price = Decimal(str(data.unit_price)
                             ) if data.unit_price is not None else None

    obj = models.Expense(
        date=data.date,
        category_id=data.category_id,
        vendor_id=data.vendor_id,

        description=desc,
        quantity=quantity if quantity is None else _qty(
            Decimal(str(quantity))),
        unit=unit,
        unit_price=unit_price if unit_price is None else _money(
            Decimal(str(unit_price))),

        apply_tax=apply_tax_bool,
        subtotal=subtotal,
        tax_amount=tax_amount,

        gallons_miles=Decimal(str(data.gallons_miles)
                              ) if data.gallons_miles is not None else None,

        expense_type=exp_type,
        payment_method=(data.payment_method if data.payment_method else None),
        receipt_url=receipt,

        payment_account_id=data.payment_account_id,

        total=total,
        notes=notes,
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    logger.info(
        "[create_expense] Inserted ID=%s | category=%s | vendor=%s | payment_account_id=%s | subtotal=%s | tax=%s | total=%s",
        obj.id, obj.category_id, obj.vendor_id, obj.payment_account_id, obj.subtotal, obj.tax_amount, obj.total
    )
    return obj


def list_expenses(db: Session):
    q = select(models.Expense).order_by(
        models.Expense.date.desc(), models.Expense.id.desc()
    )
    return db.scalars(q).all()


def update_expense(db: Session, expense_id: int, data: schemas.ExpenseUpdate):
    obj = db.get(models.Expense, expense_id)
    if not obj:
        raise ValueError("Expense not found")

    # Aplica cambios
    if data.date is not None:
        obj.date = data.date
    if data.category_id is not None:
        obj.category_id = data.category_id
    if data.vendor_id is not None:
        obj.vendor_id = data.vendor_id

    if data.description is not None:
        obj.description = data.description.strip() if data.description else None
    if data.unit is not None:
        obj.unit = data.unit.strip() if data.unit else None
    if data.expense_type is not None:
        obj.expense_type = data.expense_type.strip() if data.expense_type else None
    if data.receipt_url is not None:
        obj.receipt_url = data.receipt_url.strip() if data.receipt_url else None
    if data.notes is not None:
        obj.notes = data.notes.strip() if data.notes else None

    if data.payment_method is not None:
        obj.payment_method = data.payment_method
    if data.payment_account_id is not None:
        obj.payment_account_id = data.payment_account_id

    # Campos numéricos
    if data.quantity is not None:
        obj.quantity = _qty(Decimal(str(data.quantity)))
    if data.unit_price is not None:
        obj.unit_price = _money(Decimal(str(data.unit_price)))
    if data.gallons_miles is not None:
        obj.gallons_miles = _qty(Decimal(str(data.gallons_miles)))
    if data.apply_tax is not None:
        obj.apply_tax = data.apply_tax

    # Reglas de recalculo:
    # - Si hay unit_price y quantity -> recalcular (ignorar total manual)
    # - Si NO hay partes y viene total -> actualizar total y dejar subtotal/tax coherentes (subtotal=None, tax=0)
    has_parts = (obj.unit_price is not None and obj.quantity is not None)

    if has_parts:
        sub, tax, tot = _compute_from_parts(
            unit_price=obj.unit_price,
            quantity=obj.quantity,
            apply_tax_bool=bool(obj.apply_tax)
        )
        obj.subtotal = sub
        obj.tax_amount = tax
        obj.total = tot
    else:
        # Sin partes; permite total manual si viene en el update
        if data.total is not None:
            obj.total = _money(Decimal(str(data.total)))
        # Mantén snapshots coherentes para este caso:
        obj.subtotal = None
        obj.tax_amount = Decimal("0.00")

    db.commit()
    db.refresh(obj)
    return obj

# ---------- Payment Accounts ----------


def create_payment_account(db: Session, data: schemas.PaymentAccountIn):
    obj = models.PaymentAccount(
        name=data.name.strip(),
        type=data.type,
        provider=(data.provider.strip() if data.provider else None),
        last4=(data.last4.strip() if data.last4 else None),
        is_active=bool(data.is_active),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_payment_accounts(db: Session, types: str = None, is_active: bool = True):
    q = db.query(models.PaymentAccount)
    if is_active is not None:
        q = q.filter(models.PaymentAccount.is_active ==
                     (1 if is_active else 0))
    if types:
        type_list = [t.strip().upper() for t in types.split(",") if t.strip()]
        if type_list:
            q = q.filter(models.PaymentAccount.type.in_(type_list))
    return q.order_by(models.PaymentAccount.name.asc()).all()


def get_payment_account(db: Session, account_id: int):
    return db.get(models.PaymentAccount, account_id)


def update_payment_account(db: Session, account_id: int, data: schemas.PaymentAccountUpdate):
    obj = get_payment_account(db, account_id)
    if not obj:
        raise ValueError("Payment account not found")

    if data.name is not None:
        obj.name = data.name.strip()
    if data.type is not None:
        obj.type = data.type
    if data.provider is not None:
        obj.provider = data.provider.strip() if data.provider else None
    if data.last4 is not None:
        obj.last4 = data.last4.strip() if data.last4 else None
    if data.is_active is not None:
        obj.is_active = bool(data.is_active)

    db.commit()
    db.refresh(obj)
    return obj


def delete_payment_account(db: Session, account_id: int):
    obj = get_payment_account(db, account_id)
    if not obj:
        return
    db.delete(obj)
    db.commit()
