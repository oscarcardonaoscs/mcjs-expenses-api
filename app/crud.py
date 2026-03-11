from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, extract, func
from datetime import date, time
import calendar
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


def _minutes_between(start_time: time, end_time: time) -> int:
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute

    if end_minutes <= start_minutes:
        raise ValueError("end_time must be greater than start_time")

    return end_minutes - start_minutes


def _amount_from_minutes(minutes: int, hourly_rate) -> Decimal:
    hours = Decimal(str(minutes)) / Decimal("60")
    rate = Decimal(str(hourly_rate))
    return _money(hours * rate)


def _time_to_minutes(value: Optional[time]) -> Optional[int]:
    if value is None:
        return None
    return value.hour * 60 + value.minute


def _recalculate_helper_time_entries_for_day(
    db: Session,
    helper_id: int,
    work_date: date,
):
    entries = (
        db.query(models.HelperTimeEntry)
        .filter(
            models.HelperTimeEntry.helper_id == helper_id,
            models.HelperTimeEntry.work_date == work_date,
        )
        .order_by(
            models.HelperTimeEntry.start_time.asc(),
            models.HelperTimeEntry.id.asc(),
        )
        .all()
    )

    previous_end_minutes = None

    for entry in entries:
        start_minutes = _time_to_minutes(entry.start_time)
        end_minutes = _time_to_minutes(entry.end_time)

        if entry.start_time is not None and entry.end_time is not None:
            entry.work_minutes = _minutes_between(
                entry.start_time, entry.end_time)
        else:
            entry.work_minutes = int(entry.work_minutes or 0)

        if start_minutes is None or previous_end_minutes is None:
            entry.travel_minutes = 0
        else:
            travel_minutes = start_minutes - previous_end_minutes
            entry.travel_minutes = travel_minutes if travel_minutes > 0 else 0

        previous_end_minutes = end_minutes

    db.commit()

    for entry in entries:
        db.refresh(entry)

    return entries


def _recalculate_helper_payroll_period_totals(
    db: Session,
    payroll_id: int,
):
    payroll = (
        db.query(models.HelperPayrollPeriod)
        .options(joinedload(models.HelperPayrollPeriod.helper))
        .filter(models.HelperPayrollPeriod.id == payroll_id)
        .first()
    )

    if not payroll:
        return None

    entries = (
        db.query(models.HelperTimeEntry)
        .filter(models.HelperTimeEntry.helper_payroll_period_id == payroll_id)
        .all()
    )

    total_work_minutes = sum(int(entry.work_minutes or 0) for entry in entries)
    total_travel_minutes = sum(int(entry.travel_minutes or 0)
                               for entry in entries)

    work_rate = Decimal(str(payroll.work_rate or 0))
    travel_rate = Decimal(str(payroll.travel_rate or 0))

    payroll.total_work_minutes = total_work_minutes
    payroll.total_travel_minutes = total_travel_minutes
    payroll.work_amount = _amount_from_minutes(total_work_minutes, work_rate)
    payroll.travel_amount = _amount_from_minutes(
        total_travel_minutes, travel_rate)
    payroll.total_amount = _money(payroll.work_amount + payroll.travel_amount)

    db.commit()
    db.refresh(payroll)
    return payroll

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

    is_helpers = (data.expense_type or "").strip().lower() == "helpers"

    apply_tax_bool = False if is_helpers else (
        True if data.apply_tax is None else bool(data.apply_tax)
    )

    desc = data.description.strip() if data.description else None
    unit = data.unit.strip() if data.unit else None
    exp_type = data.expense_type.strip() if data.expense_type else None
    receipt = data.receipt_url.strip() if data.receipt_url else None
    notes = data.notes.strip() if data.notes else None

    helper_name = (data.helper_name or "").strip() or None
    task_project = (data.task_project or "").strip() or None
    paid = bool(data.paid) if data.paid is not None else False

    vendor_id = None if is_helpers else data.vendor_id

    subtotal = None
    tax_amount = Decimal("0.00")
    total = None

    if is_helpers:
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

        if not desc:
            base = []
            if helper_name:
                base.append(helper_name)
            if task_project:
                base.append(task_project)
            desc = " - ".join(base) or "Helpers payment"
    else:
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
            subtotal = None
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
            q if is_helpers else None
        ),
        unit=unit,
        unit_price=_money(Decimal(str(data.unit_price))) if data.unit_price is not None else (
            p if is_helpers else None
        ),

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
            bool(data.paid) if data.paid is not None else False
        ),

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
            E.description,
            E.helper_name,
            E.task_project,
            E.paid,
            E.quantity,
            E.unit,
            E.unit_price,
            E.apply_tax,
            E.gallons_miles,
            E.expense_type,
            E.payment_method,
            E.receipt_url,
            E.payment_account_id,
            E.subtotal,
            E.tax_amount,
            E.total,
            E.notes,
            E.created_at,
            E.updated_at,
            C.name.label("category_name"),
            V.name.label("vendor_name"),
            PA.last4.label("payment_account_last4"),
        )
        .select_from(E)
        .outerjoin(C, E.category_id == C.id)
        .outerjoin(V, E.vendor_id == V.id)
        .outerjoin(PA, E.payment_account_id == PA.id)
    )

    if category_id is not None:
        stmt = stmt.where(E.category_id == category_id)

    if month is not None:
        stmt = stmt.where(extract("month", E.date) == month)

    if year is not None:
        stmt = stmt.where(extract("year", E.date) == year)

    stmt = stmt.order_by(E.date.desc(), E.id.desc())

    rows = db.execute(stmt).mappings().all()
    return [schemas.ExpenseOut(**row) for row in rows]


def update_expense(db: Session, expense_id: int, data: schemas.ExpenseUpdate):
    obj = db.get(models.Expense, expense_id)
    if not obj:
        raise ValueError("Expense not found")

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

    if data.quantity is not None:
        obj.quantity = _qty(Decimal(str(data.quantity)))
    if data.unit_price is not None:
        obj.unit_price = _money(Decimal(str(data.unit_price)))
    if data.gallons_miles is not None:
        obj.gallons_miles = _qty(Decimal(str(data.gallons_miles)))
    if data.apply_tax is not None:
        obj.apply_tax = bool(data.apply_tax)

    is_helpers = (obj.expense_type or "").strip().lower() == "helpers"
    has_parts = (obj.unit_price is not None and obj.quantity is not None)

    if is_helpers:
        q = obj.quantity or Decimal("0")
        p = obj.unit_price or Decimal("0")
        obj.subtotal = _money(q * p)
        obj.tax_amount = Decimal("0.00")
        obj.total = obj.subtotal
        obj.apply_tax = False
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


def report_annual_expenses_by_category(db: Session, year: int) -> schemas.AnnualExpensesByCategoryResponse:
    """
    Aggregate expenses by month and category for a given year.
    """
    if not year:
        year = date.today().year

    stmt = (
        select(
            func.year(models.Expense.date).label("y"),
            func.month(models.Expense.date).label("m"),
            models.Category.name.label("category"),
            func.sum(models.Expense.total).label("total"),
        )
        .join(models.Category, models.Expense.category_id == models.Category.id)
        .where(func.year(models.Expense.date) == year)
        .group_by("y", "m", models.Category.name)
        .order_by("y", "m", models.Category.name)
    )

    rows = db.execute(stmt).all()

    buckets: dict[str, dict] = {}
    for y, m, category, total in rows:
        ym_key = f"{int(y):04d}-{int(m):02d}"
        if ym_key not in buckets:
            buckets[ym_key] = {
                "categories": {},
                "total": Decimal("0.00"),
            }

        money_total = _money(total)
        buckets[ym_key]["categories"][category] = money_total
        buckets[ym_key]["total"] = _money(
            buckets[ym_key]["total"] + money_total)

    items: list[schemas.MonthlyCategoryTotals] = []
    for ym in sorted(buckets.keys()):
        _, mm = ym.split("-")
        month_label = calendar.month_abbr[int(mm)]
        bucket = buckets[ym]

        items.append(
            schemas.MonthlyCategoryTotals(
                month=ym,
                month_label=month_label,
                categories=bucket["categories"],
                total=_money(bucket["total"]),
            )
        )

    return schemas.AnnualExpensesByCategoryResponse(year=year, items=items)


# ---------- Helpers ----------
def get_helpers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
):
    q = db.query(models.Helper)

    if is_active is not None:
        q = q.filter(models.Helper.is_active == bool(is_active))

    return q.order_by(
        models.Helper.first_name.asc(),
        models.Helper.last_name.asc()
    ).offset(skip).limit(limit).all()


def get_helper(db: Session, helper_id: int):
    return db.get(models.Helper, helper_id)


def create_helper(db: Session, helper_in: schemas.HelperCreate):
    obj = models.Helper(
        first_name=helper_in.first_name.strip(),
        last_name=helper_in.last_name.strip() if helper_in.last_name else None,
        phone=helper_in.phone.strip() if helper_in.phone else None,
        email=helper_in.email.strip() if helper_in.email else None,
        default_work_rate=_money(Decimal(str(helper_in.default_work_rate))),
        default_travel_rate=_money(
            Decimal(str(helper_in.default_travel_rate))),
        is_active=bool(helper_in.is_active),
        notes=helper_in.notes.strip() if helper_in.notes else None,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_helper(db: Session, helper_id: int, helper_in: schemas.HelperUpdate):
    obj = get_helper(db, helper_id)
    if not obj:
        return None

    if helper_in.first_name is not None:
        obj.first_name = helper_in.first_name.strip()
    if helper_in.last_name is not None:
        obj.last_name = helper_in.last_name.strip() if helper_in.last_name else None
    if helper_in.phone is not None:
        obj.phone = helper_in.phone.strip() if helper_in.phone else None
    if helper_in.email is not None:
        obj.email = helper_in.email.strip() if helper_in.email else None
    if helper_in.default_work_rate is not None:
        obj.default_work_rate = _money(
            Decimal(str(helper_in.default_work_rate)))
    if helper_in.default_travel_rate is not None:
        obj.default_travel_rate = _money(
            Decimal(str(helper_in.default_travel_rate)))
    if helper_in.is_active is not None:
        obj.is_active = bool(helper_in.is_active)
    if helper_in.notes is not None:
        obj.notes = helper_in.notes.strip() if helper_in.notes else None

    db.commit()
    db.refresh(obj)
    return obj


def delete_helper(db: Session, helper_id: int):
    obj = get_helper(db, helper_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ---------- Helper Time Entries ----------
def get_helper_time_entries(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    helper_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    unassigned_only: bool = False,
):
    q = db.query(models.HelperTimeEntry)

    if helper_id is not None:
        q = q.filter(models.HelperTimeEntry.helper_id == helper_id)

    if date_from is not None:
        q = q.filter(models.HelperTimeEntry.work_date >= date_from)

    if date_to is not None:
        q = q.filter(models.HelperTimeEntry.work_date <= date_to)

    if unassigned_only:
        q = q.filter(models.HelperTimeEntry.helper_payroll_period_id.is_(None))

    return q.order_by(
        models.HelperTimeEntry.work_date.desc(),
        models.HelperTimeEntry.start_time.desc(),
        models.HelperTimeEntry.id.desc()
    ).offset(skip).limit(limit).all()


def get_helper_time_entry(db: Session, entry_id: int):
    return db.get(models.HelperTimeEntry, entry_id)


def create_helper_time_entry(db: Session, entry_in: schemas.HelperTimeEntryCreate):
    helper = get_helper(db, entry_in.helper_id)
    if not helper:
        raise ValueError("Helper not found")

    client = get_client(db, entry_in.client_id)
    if not client:
        raise ValueError("Client not found")

    if entry_in.helper_payroll_period_id is not None:
        payroll = get_helper_payroll_period(
            db, entry_in.helper_payroll_period_id)
        if not payroll:
            raise ValueError("Helper payroll period not found")

    work_minutes = entry_in.work_minutes
    if work_minutes is None:
        if entry_in.start_time is not None and entry_in.end_time is not None:
            work_minutes = _minutes_between(
                entry_in.start_time, entry_in.end_time
            )
        else:
            work_minutes = 0

    obj = models.HelperTimeEntry(
        helper_id=entry_in.helper_id,
        client_id=entry_in.client_id,
        helper_payroll_period_id=entry_in.helper_payroll_period_id,
        work_date=entry_in.work_date,
        start_time=entry_in.start_time,
        end_time=entry_in.end_time,
        work_minutes=work_minutes,
        travel_minutes=0,
        notes=entry_in.notes.strip() if entry_in.notes else None,
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    _recalculate_helper_time_entries_for_day(
        db=db,
        helper_id=obj.helper_id,
        work_date=obj.work_date,
    )

    db.refresh(obj)
    return obj


def update_helper_time_entry(db: Session, entry_id: int, entry_in: schemas.HelperTimeEntryUpdate):
    obj = get_helper_time_entry(db, entry_id)
    if not obj:
        return None

    old_helper_id = obj.helper_id
    old_work_date = obj.work_date
    old_payroll_period_id = obj.helper_payroll_period_id

    if entry_in.helper_id is not None:
        helper = get_helper(db, entry_in.helper_id)
        if not helper:
            raise ValueError("Helper not found")
        obj.helper_id = entry_in.helper_id

    if entry_in.client_id is not None:
        client = get_client(db, entry_in.client_id)
        if not client:
            raise ValueError("Client not found")
        obj.client_id = entry_in.client_id

    if entry_in.helper_payroll_period_id is not None:
        payroll = get_helper_payroll_period(
            db, entry_in.helper_payroll_period_id
        )
        if not payroll:
            raise ValueError("Helper payroll period not found")
        obj.helper_payroll_period_id = entry_in.helper_payroll_period_id

    if entry_in.work_date is not None:
        obj.work_date = entry_in.work_date

    if entry_in.start_time is not None:
        obj.start_time = entry_in.start_time

    if entry_in.end_time is not None:
        obj.end_time = entry_in.end_time

    if entry_in.notes is not None:
        obj.notes = entry_in.notes.strip() if entry_in.notes else None

    if entry_in.work_minutes is not None:
        obj.work_minutes = entry_in.work_minutes
    elif obj.start_time is not None and obj.end_time is not None:
        obj.work_minutes = _minutes_between(obj.start_time, obj.end_time)
    else:
        obj.work_minutes = 0

    db.commit()
    db.refresh(obj)

    _recalculate_helper_time_entries_for_day(
        db=db,
        helper_id=old_helper_id,
        work_date=old_work_date,
    )

    if old_helper_id != obj.helper_id or old_work_date != obj.work_date:
        _recalculate_helper_time_entries_for_day(
            db=db,
            helper_id=obj.helper_id,
            work_date=obj.work_date,
        )

    if old_payroll_period_id is not None:
        _recalculate_helper_payroll_period_totals(
            db=db,
            payroll_id=old_payroll_period_id,
        )

    if (
        obj.helper_payroll_period_id is not None
        and obj.helper_payroll_period_id != old_payroll_period_id
    ):
        _recalculate_helper_payroll_period_totals(
            db=db,
            payroll_id=obj.helper_payroll_period_id,
        )

    db.refresh(obj)
    return obj


def delete_helper_time_entry(db: Session, entry_id: int):
    obj = get_helper_time_entry(db, entry_id)
    if not obj:
        return False

    helper_id = obj.helper_id
    work_date = obj.work_date
    payroll_id = obj.helper_payroll_period_id

    db.delete(obj)
    db.commit()

    _recalculate_helper_time_entries_for_day(
        db=db,
        helper_id=helper_id,
        work_date=work_date,
    )

    if payroll_id is not None:
        _recalculate_helper_payroll_period_totals(
            db=db,
            payroll_id=payroll_id,
        )

    return True


# ---------- Helper Payroll Periods ----------
def get_helper_payroll_periods(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    helper_id: Optional[int] = None,
    status: Optional[str] = None,
):
    q = (
        db.query(models.HelperPayrollPeriod)
        .options(joinedload(models.HelperPayrollPeriod.helper))
    )

    if helper_id is not None:
        q = q.filter(models.HelperPayrollPeriod.helper_id == helper_id)

    if status is not None:
        q = q.filter(models.HelperPayrollPeriod.status == status)

    return q.order_by(
        models.HelperPayrollPeriod.period_start.desc(),
        models.HelperPayrollPeriod.id.desc()
    ).offset(skip).limit(limit).all()


def get_helper_payroll_period(db: Session, payroll_id: int):
    return (
        db.query(models.HelperPayrollPeriod)
        .options(
            joinedload(models.HelperPayrollPeriod.helper),
            joinedload(models.HelperPayrollPeriod.time_entries).joinedload(
                models.HelperTimeEntry.helper
            ),
            joinedload(models.HelperPayrollPeriod.time_entries).joinedload(
                models.HelperTimeEntry.payroll_period
            ),
        )
        .filter(models.HelperPayrollPeriod.id == payroll_id)
        .first()
    )


def create_helper_payroll_period(db: Session, payroll_in: schemas.HelperPayrollPeriodCreate):
    helper = get_helper(db, payroll_in.helper_id)
    if not helper:
        raise ValueError("Helper not found")

    existing = db.query(models.HelperPayrollPeriod).filter(
        models.HelperPayrollPeriod.helper_id == payroll_in.helper_id,
        models.HelperPayrollPeriod.period_start == payroll_in.period_start,
        models.HelperPayrollPeriod.period_end == payroll_in.period_end,
    ).first()

    if existing:
        raise ValueError(
            "A payroll period already exists for this helper and date range")

    obj = models.HelperPayrollPeriod(
        helper_id=payroll_in.helper_id,
        period_start=payroll_in.period_start,
        period_end=payroll_in.period_end,
        pay_date=payroll_in.pay_date,
        work_rate=_money(Decimal(str(payroll_in.work_rate))),
        travel_rate=_money(Decimal(str(payroll_in.travel_rate))),
        total_work_minutes=payroll_in.total_work_minutes,
        total_travel_minutes=payroll_in.total_travel_minutes,
        work_amount=_money(Decimal(str(payroll_in.work_amount))),
        travel_amount=_money(Decimal(str(payroll_in.travel_amount))),
        total_amount=_money(Decimal(str(payroll_in.total_amount))),
        status=payroll_in.status,
        notes=payroll_in.notes.strip() if payroll_in.notes else None,
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_helper_payroll_period(db: Session, payroll_id: int, payroll_in: schemas.HelperPayrollPeriodUpdate):
    obj = get_helper_payroll_period(db, payroll_id)
    if not obj:
        return None

    if payroll_in.helper_id is not None:
        helper = get_helper(db, payroll_in.helper_id)
        if not helper:
            raise ValueError("Helper not found")
        obj.helper_id = payroll_in.helper_id

    if payroll_in.period_start is not None:
        obj.period_start = payroll_in.period_start

    if payroll_in.period_end is not None:
        obj.period_end = payroll_in.period_end

    if payroll_in.pay_date is not None:
        obj.pay_date = payroll_in.pay_date

    if payroll_in.work_rate is not None:
        obj.work_rate = _money(Decimal(str(payroll_in.work_rate)))

    if payroll_in.travel_rate is not None:
        obj.travel_rate = _money(Decimal(str(payroll_in.travel_rate)))

    if payroll_in.total_work_minutes is not None:
        obj.total_work_minutes = payroll_in.total_work_minutes

    if payroll_in.total_travel_minutes is not None:
        obj.total_travel_minutes = payroll_in.total_travel_minutes

    if payroll_in.work_amount is not None:
        obj.work_amount = _money(Decimal(str(payroll_in.work_amount)))

    if payroll_in.travel_amount is not None:
        obj.travel_amount = _money(Decimal(str(payroll_in.travel_amount)))

    if payroll_in.total_amount is not None:
        obj.total_amount = _money(Decimal(str(payroll_in.total_amount)))

    if payroll_in.status is not None:
        obj.status = payroll_in.status

    if payroll_in.notes is not None:
        obj.notes = payroll_in.notes.strip() if payroll_in.notes else None

    db.commit()
    db.refresh(obj)
    return obj


def delete_helper_payroll_period(db: Session, payroll_id: int):
    obj = get_helper_payroll_period(db, payroll_id)
    if not obj:
        return False

    db.query(models.HelperTimeEntry).filter(
        models.HelperTimeEntry.helper_payroll_period_id == payroll_id
    ).update(
        {models.HelperTimeEntry.helper_payroll_period_id: None},
        synchronize_session=False
    )

    db.delete(obj)
    db.commit()
    return True


def generate_helper_payroll_period(
    db: Session,
    helper_id: int,
    period_start: date,
    period_end: date,
    pay_date: Optional[date] = None,
):
    helper = get_helper(db, helper_id)
    if not helper:
        raise ValueError("Helper not found")

    existing = db.query(models.HelperPayrollPeriod).filter(
        models.HelperPayrollPeriod.helper_id == helper_id,
        models.HelperPayrollPeriod.period_start == period_start,
        models.HelperPayrollPeriod.period_end == period_end,
    ).first()

    if existing:
        raise ValueError(
            "A payroll period already exists for this helper and date range")

    entries = db.query(models.HelperTimeEntry).filter(
        models.HelperTimeEntry.helper_id == helper_id,
        models.HelperTimeEntry.work_date >= period_start,
        models.HelperTimeEntry.work_date <= period_end,
        models.HelperTimeEntry.helper_payroll_period_id.is_(None),
    ).order_by(
        models.HelperTimeEntry.work_date.asc(),
        models.HelperTimeEntry.start_time.asc(),
        models.HelperTimeEntry.id.asc()
    ).all()

    if not entries:
        return None

    total_work_minutes = sum(int(entry.work_minutes or 0) for entry in entries)
    total_travel_minutes = sum(int(entry.travel_minutes or 0)
                               for entry in entries)

    work_rate = _money(Decimal(str(helper.default_work_rate)))
    travel_rate = _money(Decimal(str(helper.default_travel_rate)))

    work_amount = _amount_from_minutes(total_work_minutes, work_rate)
    travel_amount = _amount_from_minutes(total_travel_minutes, travel_rate)
    total_amount = _money(work_amount + travel_amount)

    payroll = models.HelperPayrollPeriod(
        helper_id=helper_id,
        period_start=period_start,
        period_end=period_end,
        pay_date=pay_date,
        work_rate=work_rate,
        travel_rate=travel_rate,
        total_work_minutes=total_work_minutes,
        total_travel_minutes=total_travel_minutes,
        work_amount=work_amount,
        travel_amount=travel_amount,
        total_amount=total_amount,
        status="Ready",
        notes=None,
    )

    db.add(payroll)
    db.flush()

    for entry in entries:
        entry.helper_payroll_period_id = payroll.id

    db.commit()
    _recalculate_helper_payroll_period_totals(db=db, payroll_id=payroll.id)
    db.refresh(payroll)
    return payroll


def mark_helper_payroll_period_paid(
    db: Session,
    payroll_id: int,
    pay_date: date,
):
    payroll = get_helper_payroll_period(db, payroll_id)
    if not payroll:
        return None

    payroll.pay_date = pay_date
    payroll.status = "Paid"

    db.commit()
    db.refresh(payroll)
    return payroll


def get_clients(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Client)
        .order_by(models.Client.name)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_client(db: Session, client_id: int):
    return db.query(models.Client).filter(models.Client.id == client_id).first()


def get_client_by_name(db: Session, name: str):
    return (
        db.query(models.Client)
        .filter(func.lower(models.Client.name) == name.lower())
        .first()
    )


def create_client(db: Session, client: schemas.ClientCreate):
    db_client = models.Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


def update_client(db: Session, client_id: int, client: schemas.ClientUpdate):
    db_client = get_client(db, client_id)

    if not db_client:
        return None

    update_data = client.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_client, key, value)

    db.commit()
    db.refresh(db_client)

    return db_client


def delete_client(db: Session, client_id: int):
    db_client = get_client(db, client_id)

    if not db_client:
        return None

    db.delete(db_client)
    db.commit()

    return db_client
