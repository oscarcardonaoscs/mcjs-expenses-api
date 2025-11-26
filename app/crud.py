from sqlalchemy.orm import Session
from sqlalchemy import select, extract
from . import models, schemas
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

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

    # Helpers?
    is_helpers = (data.expense_type or "").strip().lower() == "helpers"

    # apply_tax: para helpers forzamos False
    apply_tax_bool = False if is_helpers else (
        True if data.apply_tax is None else bool(data.apply_tax))

    # Normaliza strings
    desc = data.description.strip() if data.description else None
    unit = data.unit.strip() if data.unit else None
    exp_type = data.expense_type.strip() if data.expense_type else None
    receipt = data.receipt_url.strip() if data.receipt_url else None
    notes = data.notes.strip() if data.notes else None

    # Helpers extras
    helper_name = (data.helper_name or "").strip() or None
    task_project = (data.task_project or "").strip() or None
    paid = bool(data.paid) if data.paid is not None else False

    # Vendor: en Helpers normalmente no aplica
    vendor_id = None if is_helpers else data.vendor_id

    subtotal = None
    tax_amount = Decimal("0.00")
    total = None

    # ---- MONTOS ----
    if is_helpers:
        # Requiere horas y rate (quantity y unit_price)
        q = Decimal(str(data.quantity)
                    ) if data.quantity is not None else Decimal("0")
        p = Decimal(str(data.unit_price)
                    ) if data.unit_price is not None else Decimal("0")
        q = _qty(q)
        p = _money(p)
        subtotal = _money(q * p)
        tax_amount = Decimal("0.00")
        total = subtotal
        unit = "hour" if not unit else unit
        # autodescripción si viene vacío
        if not desc:
            base = []
            if helper_name:
                base.append(helper_name)
            if task_project:
                base.append(task_project)
            desc = " - ".join(base) or "Helpers payment"
    else:
        # No-Helpers: partes o total manual
        if data.unit_price is not None and data.quantity is not None:
            subtotal, tax_amount, total = _compute_from_parts(
                unit_price=data.unit_price,
                quantity=data.quantity,
                apply_tax_bool=apply_tax_bool
            )
            quantity = _qty(Decimal(str(data.quantity)))
            unit_price = _money(Decimal(str(data.unit_price)))
        else:
            if data.total is None:
                raise ValueError(
                    "Either (unit_price & quantity) or total must be provided.")
            total = _money(Decimal(str(data.total)))
            quantity = Decimal(str(data.quantity)
                               ) if data.quantity is not None else None
            unit_price = Decimal(str(data.unit_price)
                                 ) if data.unit_price is not None else None
            subtotal = None  # cuando viene total manual
            tax_amount = Decimal("0.00")

    obj = models.Expense(
        date=data.date,
        category_id=data.category_id,
        vendor_id=vendor_id,

        description=desc,
        helper_name=helper_name if is_helpers else (data.helper_name or None),
        task_project=task_project if is_helpers else (
            data.task_project or None),

        quantity=_qty(Decimal(str(data.quantity))) if data.quantity is not None else (
            q if is_helpers else None),
        unit=unit,
        unit_price=_money(Decimal(str(data.unit_price))) if data.unit_price is not None else (
            p if is_helpers else None),

        apply_tax=apply_tax_bool,
        subtotal=subtotal,
        tax_amount=tax_amount,

        gallons_miles=_qty(Decimal(str(data.gallons_miles))
                           ) if data.gallons_miles is not None else None,

        expense_type=exp_type,
        payment_method=(data.payment_method if data.payment_method else None),
        receipt_url=receipt,

        payment_account_id=data.payment_account_id,
        paid=paid if is_helpers else (
            bool(data.paid) if data.paid is not None else False),

        total=total,
        notes=notes,
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    logger.info(
        "[create_expense] Inserted ID=%s | type=%s | subtotal=%s | tax=%s | total=%s",
        obj.id, obj.expense_type, obj.subtotal, obj.tax_amount, obj.total
    )
    return obj


def list_expenses(
    db: Session,
    category_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
):
    E = models.Expense
    C = models.Category
    V = models.Vendor
    PA = models.PaymentAccount

    stmt = (
        select(
            E.id,
            E.date,
            E.category_id,
            E.vendor_id,
            E.expense_type,
            E.description,
            E.total,
            E.payment_method,
            E.payment_account_id,
            C.name.label("category_name"),
            V.name.label("vendor_name"),
            PA.last4.label("payment_account_last4"),
        )
        .select_from(E)
        .outerjoin(C, E.category_id == C.id)
        .outerjoin(V, E.vendor_id == V.id)
        .outerjoin(PA, E.payment_account_id == PA.id)
        .order_by(E.date.desc(), E.id.desc())
    )

    # ---------- Filtros dinámicos ----------
    if category_id is not None:
        stmt = stmt.where(E.category_id == category_id)

    if month is not None:
        # E.date es Date, usamos extract('month', date)
        stmt = stmt.where(extract("month", E.date) == month)

    if year is not None:
        stmt = stmt.where(extract("year", E.date) == year)

    # Orden final (más reciente primero)
    stmt = stmt.order_by(E.date.desc(), E.id.desc())

    # mappings() devuelve dicts por fila
    rows = db.execute(stmt).mappings().all()
    return [schemas.ExpenseOut(**row) for row in rows]


def update_expense(db: Session, expense_id: int, data: schemas.ExpenseUpdate):
    obj = db.get(models.Expense, expense_id)
    if not obj:
        raise ValueError("Expense not found")

    # Cambios simples
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

    # Helpers extras
    if data.helper_name is not None:
        obj.helper_name = data.helper_name.strip() if data.helper_name else None
    if data.task_project is not None:
        obj.task_project = data.task_project.strip() if data.task_project else None
    if data.paid is not None:
        obj.paid = bool(data.paid)

    if data.payment_method is not None:
        obj.payment_method = data.payment_method
    if data.payment_account_id is not None:
        obj.payment_account_id = data.payment_account_id

    # Numéricos
    if data.quantity is not None:
        obj.quantity = _qty(Decimal(str(data.quantity)))
    if data.unit_price is not None:
        obj.unit_price = _money(Decimal(str(data.unit_price)))
    if data.gallons_miles is not None:
        obj.gallons_miles = _qty(Decimal(str(data.gallons_miles)))
    if data.apply_tax is not None:
        obj.apply_tax = bool(data.apply_tax)

    # ---- Reglas por tipo ----
    is_helpers = (obj.expense_type or "").strip().lower() == "helpers"
    has_parts = (obj.unit_price is not None and obj.quantity is not None)

    if is_helpers:
        # Forzar sin TAX, total = horas * rate
        q = obj.quantity or Decimal("0")
        p = obj.unit_price or Decimal("0")
        obj.subtotal = _money(q * p)
        obj.tax_amount = Decimal("0.00")
        obj.total = obj.subtotal
        obj.apply_tax = False
        # Vendor normalmente no aplica
        # (si quieres forzarlo a NULL, descomenta la línea)
        # obj.vendor_id = None
    else:
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
            # Permite total manual
            if data.total is not None:
                obj.total = _money(Decimal(str(data.total)))
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
