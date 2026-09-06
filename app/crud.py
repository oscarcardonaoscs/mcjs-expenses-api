from sqlalchemy.orm import Session, joinedload, selectinload
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


# ---------- Expense Concepts ----------
def _find_duplicate_expense_concept(
    db: Session,
    category_id: int,
    name: str,
    exclude_id: Optional[int] = None,
):
    q = (
        db.query(models.ExpenseConcept)
        .filter(
            models.ExpenseConcept.category_id == category_id,
            func.lower(models.ExpenseConcept.name) == name.lower(),
        )
    )

    if exclude_id is not None:
        q = q.filter(models.ExpenseConcept.id != exclude_id)

    return q.first()


def create_expense_concept(
    db: Session,
    data: schemas.ExpenseConceptCreate,
):
    category = get_category(db, data.category_id)

    if not category:
        raise ValueError("Category not found")

    name = data.name.strip()

    existing = _find_duplicate_expense_concept(
        db=db,
        category_id=data.category_id,
        name=name,
    )

    if existing:
        raise ValueError(
            "An expense concept with this name already exists "
            "for the selected category"
        )

    obj = models.ExpenseConcept(
        category_id=data.category_id,
        name=name,
        is_active=bool(data.is_active),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return get_expense_concept(db, obj.id)


def list_expense_concepts(
    db: Session,
    category_id: Optional[int] = None,
    is_active: Optional[bool] = True,
):
    q = (
        db.query(models.ExpenseConcept)
        .options(joinedload(models.ExpenseConcept.category))
    )

    if category_id is not None:
        q = q.filter(models.ExpenseConcept.category_id == category_id)

    if is_active is not None:
        q = q.filter(models.ExpenseConcept.is_active == bool(is_active))

    return (
        q.order_by(
            models.ExpenseConcept.name.asc(),
            models.ExpenseConcept.id.asc(),
        )
        .all()
    )


def get_expense_concept(
    db: Session,
    expense_concept_id: int,
):
    return (
        db.query(models.ExpenseConcept)
        .options(joinedload(models.ExpenseConcept.category))
        .filter(models.ExpenseConcept.id == expense_concept_id)
        .first()
    )


def update_expense_concept(
    db: Session,
    expense_concept_id: int,
    data: schemas.ExpenseConceptUpdate,
):
    obj = get_expense_concept(db, expense_concept_id)

    if not obj:
        return None

    category_id = (
        data.category_id
        if data.category_id is not None
        else obj.category_id
    )
    name = data.name.strip() if data.name is not None else obj.name

    if data.category_id is not None:
        category = get_category(db, data.category_id)
        if not category:
            raise ValueError("Category not found")

    existing = _find_duplicate_expense_concept(
        db=db,
        category_id=category_id,
        name=name,
        exclude_id=obj.id,
    )

    if existing:
        raise ValueError(
            "An expense concept with this name already exists "
            "for the selected category"
        )

    if data.category_id is not None:
        obj.category_id = data.category_id

    if data.name is not None:
        obj.name = name

    if data.is_active is not None:
        obj.is_active = bool(data.is_active)

    db.commit()
    db.refresh(obj)

    return get_expense_concept(db, obj.id)


def delete_expense_concept(
    db: Session,
    expense_concept_id: int,
):
    obj = get_expense_concept(db, expense_concept_id)

    if not obj:
        return False

    # Soft delete so historical expenses keep their concept relation.
    obj.is_active = False

    db.commit()
    db.refresh(obj)

    return True


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
def _validate_expense_concept(
    db: Session,
    expense_concept_id: int,
    category_id: Optional[int],
    require_active: bool = True,
):
    concept = get_expense_concept(db, expense_concept_id)

    if not concept:
        raise ValueError("Expense concept not found")

    if require_active and not concept.is_active:
        raise ValueError("Expense concept is inactive")

    if category_id is None:
        raise ValueError(
            "category_id is required when expense_concept_id is provided"
        )

    if concept.category_id != category_id:
        raise ValueError(
            "Expense concept does not belong to the selected category"
        )

    return concept


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

    if data.expense_concept_id is not None:
        _validate_expense_concept(
            db=db,
            expense_concept_id=data.expense_concept_id,
            category_id=data.category_id,
            require_active=True,
        )

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
        expense_concept_id=data.expense_concept_id,
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
    EC = models.ExpenseConcept
    V = models.Vendor
    PA = models.PaymentAccount

    stmt = (
        select(
            E.id,
            E.date,
            E.category_id,
            E.expense_concept_id,
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
            EC.name.label("expense_concept_name"),
            V.name.label("vendor_name"),
            PA.last4.label("payment_account_last4"),
        )
        .select_from(E)
        .outerjoin(C, E.category_id == C.id)
        .outerjoin(EC, E.expense_concept_id == EC.id)
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

    fields_set = data.model_fields_set

    new_category_id = (
        data.category_id
        if "category_id" in fields_set
        else obj.category_id
    )
    new_expense_concept_id = (
        data.expense_concept_id
        if "expense_concept_id" in fields_set
        else obj.expense_concept_id
    )

    if new_expense_concept_id is not None and (
        "expense_concept_id" in fields_set
        or "category_id" in fields_set
    ):
        _validate_expense_concept(
            db=db,
            expense_concept_id=new_expense_concept_id,
            category_id=new_category_id,
            require_active="expense_concept_id" in fields_set,
        )

    if data.date is not None:
        obj.date = data.date

    if "category_id" in fields_set:
        obj.category_id = data.category_id

    if "expense_concept_id" in fields_set:
        obj.expense_concept_id = data.expense_concept_id

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


def delete_expense(db: Session, expense_id: int):
    obj = db.get(models.Expense, expense_id)

    if not obj:
        return False

    db.delete(obj)
    db.commit()

    return True

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
    client_id: Optional[int] = None,
    payroll_status: Optional[str] = None,
):
    TimeEntry = models.HelperTimeEntry
    Helper = models.Helper
    Client = models.Client
    WorkEvent = models.HelperWorkEvent
    Location = models.ClientLocation
    Payroll = models.HelperPayrollPeriod

    q = (
        db.query(
            TimeEntry.id.label("id"),
            TimeEntry.helper_id.label("helper_id"),
            TimeEntry.work_event_id.label("work_event_id"),
            TimeEntry.helper_payroll_period_id.label(
                "helper_payroll_period_id"
            ),
            TimeEntry.work_date.label("work_date"),
            TimeEntry.client_id.label("client_id"),
            TimeEntry.start_time.label("start_time"),
            TimeEntry.end_time.label("end_time"),
            TimeEntry.work_minutes.label("work_minutes"),
            TimeEntry.created_at.label("created_at"),
            TimeEntry.updated_at.label("updated_at"),

            Client.name.label("client_name"),

            Helper.first_name.label("helper_first_name"),
            Helper.last_name.label("helper_last_name"),

            WorkEvent.location_id.label("location_id"),
            WorkEvent.service_amount.label("service_amount"),
            WorkEvent.service_type.label("service_type"),
            WorkEvent.service_frequency.label("service_frequency"),
            WorkEvent.payment_method.label("payment_method"),
            WorkEvent.payment_status.label("stored_payment_status"),
            WorkEvent.payment_received_date.label(
                "payment_received_date"
            ),

            Location.location_name.label("location_name"),

            Payroll.period_start.label("payroll_period_start"),
            Payroll.period_end.label("payroll_period_end"),
            Payroll.status.label("payroll_status"),
        )
        .select_from(TimeEntry)
        .outerjoin(
            Helper,
            TimeEntry.helper_id == Helper.id,
        )
        .outerjoin(
            Client,
            TimeEntry.client_id == Client.id,
        )
        .outerjoin(
            WorkEvent,
            TimeEntry.work_event_id == WorkEvent.id,
        )
        .outerjoin(
            Location,
            WorkEvent.location_id == Location.id,
        )
        .outerjoin(
            Payroll,
            TimeEntry.helper_payroll_period_id == Payroll.id,
        )
    )

    if helper_id is not None:
        q = q.filter(
            TimeEntry.helper_id == helper_id
        )

    if client_id is not None:
        q = q.filter(
            TimeEntry.client_id == client_id
        )

    if payroll_status == "Pending":
        q = q.filter(
            TimeEntry.helper_payroll_period_id.is_(None)
        )

    elif payroll_status == "Ready":
        q = q.filter(
            Payroll.status == "Ready"
        )

    elif payroll_status == "Paid":
        q = q.filter(
            Payroll.status == "Paid"
        )

    rows = (
        q.order_by(
            TimeEntry.work_date.desc(),
            TimeEntry.start_time.desc(),
            TimeEntry.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []

    for row in rows:
        helper_name_parts = [
            (row.helper_first_name or "").strip(),
            (row.helper_last_name or "").strip(),
        ]

        helper_name = " ".join(
            part
            for part in helper_name_parts
            if part
        ) or None

        # Planned is a display-only state.
        # It means the service has not been performed yet.
        if row.start_time is None or row.end_time is None:
            client_payment_status = "Planned"
        else:
            client_payment_status = (
                row.stored_payment_status or "Pending"
            )

        results.append(
            schemas.HelperTimeEntryResponse(
                id=row.id,

                helper_id=row.helper_id,
                helper_name=helper_name,

                work_event_id=row.work_event_id,
                helper_payroll_period_id=(
                    row.helper_payroll_period_id
                ),

                work_date=row.work_date,

                client_id=row.client_id,
                client_name=row.client_name,

                location_id=row.location_id,
                location_name=row.location_name,

                start_time=row.start_time,
                end_time=row.end_time,
                work_minutes=int(row.work_minutes or 0),

                service_amount=row.service_amount,
                service_type=row.service_type,
                service_frequency=row.service_frequency,

                payment_method=row.payment_method,
                client_payment_status=client_payment_status,
                payment_received_date=(
                    row.payment_received_date
                ),

                payroll_period_start=(
                    row.payroll_period_start
                ),
                payroll_period_end=row.payroll_period_end,
                payroll_status=row.payroll_status,

                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )

    return results


def get_helper_time_entry(db: Session, entry_id: int):
    return db.get(models.HelperTimeEntry, entry_id)


def create_helper_time_entry(
    db: Session,
    entry_in: schemas.HelperTimeEntryCreate,
):
    def calculate_work_minutes(start_time, end_time):
        if start_time is None or end_time is None:
            return 0

        start_total_minutes = (
            start_time.hour * 60
            + start_time.minute
        )

        end_total_minutes = (
            end_time.hour * 60
            + end_time.minute
        )

        return max(
            end_total_minutes - start_total_minutes,
            0,
        )

    default_work_minutes = calculate_work_minutes(
        entry_in.start_time,
        entry_in.end_time,
    )

    work_event = models.HelperWorkEvent(
        client_id=entry_in.client_id,
        work_date=entry_in.work_date,
        start_time=entry_in.start_time,
        end_time=entry_in.end_time,
        notes=entry_in.notes,
    )

    db.add(work_event)
    db.flush()

    created_entries = []
    affected_helper_ids = set()

    for helper_entry in entry_in.helpers:
        helper = get_helper(
            db,
            helper_entry.helper_id,
        )

        if not helper:
            raise ValueError(
                f"Helper not found: {helper_entry.helper_id}"
            )

        work_minutes = helper_entry.work_minutes

        if work_minutes is None:
            work_minutes = default_work_minutes

        db_entry = models.HelperTimeEntry(
            helper_id=helper_entry.helper_id,
            work_event_id=work_event.id,
            helper_payroll_period_id=None,

            # Compatibilidad temporal
            client_id=entry_in.client_id,
            work_date=entry_in.work_date,
            start_time=entry_in.start_time,
            end_time=entry_in.end_time,

            work_minutes=work_minutes,

            # Se inicializa en 0.
            # El recálculo diario determina el valor real.
            travel_minutes=0,

            notes=helper_entry.notes,
        )

        db.add(db_entry)

        created_entries.append(db_entry)
        affected_helper_ids.add(
            helper_entry.helper_id
        )

    db.commit()

    # Recalcular la jornada completa de cada helper.
    for helper_id in affected_helper_ids:
        _recalculate_helper_time_entries_for_day(
            db=db,
            helper_id=helper_id,
            work_date=entry_in.work_date,
        )

    for db_entry in created_entries:
        db.refresh(db_entry)

    return {
        "work_event_id": work_event.id,
        "entries": created_entries,
    }


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
def _get_expense_category_by_name(db: Session, name: str):
    return (
        db.query(models.Category)
        .filter(func.lower(models.Category.name) == name.lower())
        .first()
    )


def _get_expense_helper_payroll_link(db: Session, payroll_id: int):
    return (
        db.query(models.ExpenseHelperPayrollLink)
        .filter(
            models.ExpenseHelperPayrollLink.helper_payroll_period_id == payroll_id
        )
        .first()
    )


def _build_helper_payroll_expense_payload(payroll) -> schemas.ExpenseCreate:
    helper_name_parts = [
        (payroll.helper.first_name or "").strip(),
        (payroll.helper.last_name or "").strip(
        ) if payroll.helper.last_name else "",
    ]
    helper_name = " ".join(
        [p for p in helper_name_parts if p]).strip() or "Helper"

    description = "Worked {} to {}".format(
        payroll.period_start.isoformat(),
        payroll.period_end.isoformat(),
    )

    return schemas.ExpenseCreate(
        date=payroll.pay_date,
        total=payroll.total_amount,
        notes=payroll.notes,
        category_id=150001,  # Helpers
        vendor_id=None,
        description=description,
        helper_name=helper_name,
        task_project="Payroll",
        quantity=Decimal("1.000"),
        apply_tax=False,
        subtotal=payroll.total_amount,
        tax_amount=Decimal("0.00"),
        unit="payroll",
        unit_price=payroll.total_amount,
        gallons_miles=None,
        expense_type="Helpers",
        payment_method="CASH",
        payment_account_id=1,  # Default account
        paid=True,
        receipt_url=None,
    )


def _ensure_expense_for_helper_payroll(
    db: Session,
    payroll,
):
    existing_link = _get_expense_helper_payroll_link(db, payroll.id)
    if existing_link:
        return existing_link

    category = _get_expense_category_by_name(db, "Helpers")
    if not category:
        raise ValueError("Category 'Helpers' not found")

    expense_data = _build_helper_payroll_expense_payload(payroll)
    expense_data.category_id = category.id

    expense = create_expense(db, expense_data)

    link = models.ExpenseHelperPayrollLink(
        expense_id=expense.id,
        helper_payroll_period_id=payroll.id,
    )

    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def _delete_expense_for_helper_payroll(
    db: Session,
    payroll_id: int,
):
    link = _get_expense_helper_payroll_link(db, payroll_id)
    if not link:
        return False

    expense = db.get(models.Expense, link.expense_id)

    db.delete(link)

    if expense:
        db.delete(expense)

    db.commit()
    return True


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

    old_status = obj.status

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

    new_status = obj.status

    if old_status == "Paid" and new_status != "Paid":
        obj.pay_date = None

    db.commit()
    db.refresh(obj)

    if old_status != "Paid" and new_status == "Paid":
        if obj.pay_date is None:
            raise ValueError(
                "pay_date is required when marking payroll as Paid")
        _ensure_expense_for_helper_payroll(db, obj)

    elif old_status == "Paid" and new_status != "Paid":
        _delete_expense_for_helper_payroll(db, obj.id)

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
    # ---------------------------------------------------------
    # 1. Validar que el helper exista
    # ---------------------------------------------------------
    helper = get_helper(db, helper_id)

    if not helper:
        raise ValueError("Helper not found")

    # ---------------------------------------------------------
    # 2. Validar que no exista ya un payroll para ese periodo
    # ---------------------------------------------------------
    existing = (
        db.query(models.HelperPayrollPeriod)
        .filter(
            models.HelperPayrollPeriod.helper_id == helper_id,
            models.HelperPayrollPeriod.period_start == period_start,
            models.HelperPayrollPeriod.period_end == period_end,
        )
        .first()
    )

    if existing:
        raise ValueError(
            "A payroll period already exists for this helper and date range"
        )

    # ---------------------------------------------------------
    # 3. Buscar todos los días distintos con Time Entries
    #    disponibles dentro del periodo.
    # ---------------------------------------------------------
    work_dates = (
        db.query(models.HelperTimeEntry.work_date)
        .filter(
            models.HelperTimeEntry.helper_id == helper_id,
            models.HelperTimeEntry.work_date >= period_start,
            models.HelperTimeEntry.work_date <= period_end,
            models.HelperTimeEntry.helper_payroll_period_id.is_(None),
        )
        .distinct()
        .all()
    )

    # ---------------------------------------------------------
    # 4. Recalcular work_minutes y travel_minutes
    #    de cada día antes de generar el payroll.
    # ---------------------------------------------------------
    for (work_date,) in work_dates:
        _recalculate_helper_time_entries_for_day(
            db=db,
            helper_id=helper_id,
            work_date=work_date,
        )

    # ---------------------------------------------------------
    # 5. Volver a consultar los entries después del recálculo.
    #
    # Esto es importante porque ahora travel_minutes ya contiene
    # los valores corregidos.
    # ---------------------------------------------------------
    entries = (
        db.query(models.HelperTimeEntry)
        .filter(
            models.HelperTimeEntry.helper_id == helper_id,
            models.HelperTimeEntry.work_date >= period_start,
            models.HelperTimeEntry.work_date <= period_end,
            models.HelperTimeEntry.helper_payroll_period_id.is_(None),
        )
        .order_by(
            models.HelperTimeEntry.work_date.asc(),
            models.HelperTimeEntry.start_time.asc(),
            models.HelperTimeEntry.id.asc(),
        )
        .all()
    )

    if not entries:
        return None

    # ---------------------------------------------------------
    # 6. Calcular totales de minutos
    # ---------------------------------------------------------
    total_work_minutes = sum(
        int(entry.work_minutes or 0)
        for entry in entries
    )

    total_travel_minutes = sum(
        int(entry.travel_minutes or 0)
        for entry in entries
    )

    # ---------------------------------------------------------
    # 7. Obtener rates actuales del helper
    # ---------------------------------------------------------
    work_rate = _money(
        Decimal(str(helper.default_work_rate))
    )

    travel_rate = _money(
        Decimal(str(helper.default_travel_rate))
    )

    # ---------------------------------------------------------
    # 8. Calcular montos
    # ---------------------------------------------------------
    work_amount = _amount_from_minutes(
        total_work_minutes,
        work_rate,
    )

    travel_amount = _amount_from_minutes(
        total_travel_minutes,
        travel_rate,
    )

    total_amount = _money(
        work_amount + travel_amount
    )

    # ---------------------------------------------------------
    # 9. Crear el Payroll Period
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 10. Asociar los Time Entries al Payroll recién creado
    # ---------------------------------------------------------
    for entry in entries:
        entry.helper_payroll_period_id = payroll.id

    # ---------------------------------------------------------
    # 11. Guardar cambios
    # ---------------------------------------------------------
    db.commit()

    # ---------------------------------------------------------
    # 12. Recalcular nuevamente los totales del payroll
    #     desde los entries asociados.
    #
    # Esto mantiene una sola lógica de consolidación.
    # ---------------------------------------------------------
    _recalculate_helper_payroll_period_totals(
        db=db,
        payroll_id=payroll.id,
    )

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

    _ensure_expense_for_helper_payroll(db, payroll)

    db.refresh(payroll)
    return payroll


def get_clients(db: Session):
    return (
        db.query(models.Client)
        .options(
            selectinload(models.Client.locations)
        )
        .order_by(models.Client.name.asc())
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
    data = client.model_dump()

    print("========== CREATE CLIENT DEBUG ==========")
    print("models file:", models.__file__)
    print("Client columns:", list(models.Client.__table__.columns.keys()))
    print("Payload:", data)
    print("=========================================")

    db_client = models.Client(**data)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


def update_client(db: Session, client_id: int, client_update: schemas.ClientUpdate):
    db_client = get_client(db, client_id)

    if not db_client:
        return None

    update_data = client_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_client, field, value)

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

# ---------- Client Locations ----------


def get_client_locations(
    db: Session,
    client_id: int,
    include_inactive: bool = False,
):
    q = db.query(models.ClientLocation).filter(
        models.ClientLocation.client_id == client_id
    )

    if not include_inactive:
        q = q.filter(models.ClientLocation.is_active == True)

    return (
        q.order_by(
            models.ClientLocation.is_primary.desc(),
            models.ClientLocation.location_name.asc(),
            models.ClientLocation.id.asc(),
        )
        .all()
    )


def get_client_location(db: Session, location_id: int):
    return (
        db.query(models.ClientLocation)
        .filter(models.ClientLocation.id == location_id)
        .first()
    )


def create_client_location(
    db: Session,
    client_id: int,
    location_in: schemas.ClientLocationCreate,
):
    client = get_client(db, client_id)

    if not client:
        raise ValueError("Client not found")

    existing_location = (
        db.query(models.ClientLocation)
        .filter(models.ClientLocation.client_id == client_id)
        .first()
    )

    data = location_in.model_dump()

    if data.get("access_notes"):
        data["access_notes"] = data["access_notes"].strip() or None

    if data.get("service_notes"):
        data["service_notes"] = data["service_notes"].strip() or None

    # If this is the first location for the client, make it primary.
    if not existing_location:
        data["is_primary"] = True

    # If the new location is primary, remove primary from the others.
    if data.get("is_primary") is True:
        (
            db.query(models.ClientLocation)
            .filter(models.ClientLocation.client_id == client_id)
            .update(
                {models.ClientLocation.is_primary: False},
                synchronize_session=False,
            )
        )

    db_location = models.ClientLocation(
        client_id=client_id,
        **data,
    )

    db.add(db_location)
    db.commit()
    db.refresh(db_location)

    return db_location


def update_client_location(
    db: Session,
    location_id: int,
    location_in: schemas.ClientLocationUpdate,
):
    db_location = get_client_location(db, location_id)

    if not db_location:
        return None

    update_data = location_in.model_dump(exclude_unset=True)

    if update_data.get("access_notes"):
        update_data["access_notes"] = update_data["access_notes"].strip() or None

    if update_data.get("service_notes"):
        update_data["service_notes"] = update_data["service_notes"].strip() or None

    # If this location is being marked as primary,
    # remove primary from the other locations for the same client.
    if update_data.get("is_primary") is True:
        (
            db.query(models.ClientLocation)
            .filter(
                models.ClientLocation.client_id == db_location.client_id,
                models.ClientLocation.id != db_location.id,
            )
            .update(
                {models.ClientLocation.is_primary: False},
                synchronize_session=False,
            )
        )

    for key, value in update_data.items():
        setattr(db_location, key, value)

    db.commit()
    db.refresh(db_location)

    return db_location


def delete_client_location(db: Session, location_id: int):
    db_location = get_client_location(db, location_id)

    if not db_location:
        return None

    was_primary = bool(db_location.is_primary)
    client_id = db_location.client_id

    # Soft delete
    db_location.is_active = False
    db_location.is_primary = False

    if was_primary:
        replacement = (
            db.query(models.ClientLocation)
            .filter(
                models.ClientLocation.client_id == client_id,
                models.ClientLocation.id != location_id,
                models.ClientLocation.is_active == True,
            )
            .order_by(models.ClientLocation.id.asc())
            .first()
        )

        if replacement:
            replacement.is_primary = True

    db.commit()
    db.refresh(db_location)

    return db_location


def create_helper_work_event(
    db: Session,
    work_event: schemas.HelperWorkEventCreate,
):
    # ---------------------------------------------------------
    # 1. Validar helpers antes de crear cualquier registro
    # ---------------------------------------------------------
    helper_ids = {
        helper_item.helper_id
        for helper_item in work_event.helpers
    }

    for helper_id in helper_ids:
        helper = get_helper(db, helper_id)

        if not helper:
            raise ValueError(
                f"Helper not found: {helper_id}"
            )

    # ---------------------------------------------------------
    # 2. Validar Location
    # ---------------------------------------------------------
    location = (
        db.query(models.ClientLocation)
        .filter(
            models.ClientLocation.id == work_event.location_id,
            models.ClientLocation.client_id == work_event.client_id,
            models.ClientLocation.is_active.is_(True),
        )
        .first()
    )

    if not location:
        raise ValueError(
            "The selected location does not belong to the selected "
            "client or is inactive."
        )

    # ---------------------------------------------------------
    # 3. Calcular minutos de trabajo por defecto
    # ---------------------------------------------------------
    default_work_minutes = 0

    if (
        work_event.start_time is not None
        and work_event.end_time is not None
    ):
        default_work_minutes = _minutes_between(
            work_event.start_time,
            work_event.end_time,
        )

    # ---------------------------------------------------------
    # 4. Normalizar información de pago
    # ---------------------------------------------------------
    payment_status = work_event.payment_status or "Pending"
    payment_received_date = work_event.payment_received_date

    if payment_status == "Collected" and payment_received_date is None:
        payment_received_date = work_event.work_date
    elif payment_status == "Pending":
        payment_received_date = None

    # ---------------------------------------------------------
    # 5. Crear el Work Event
    # ---------------------------------------------------------
    db_event = models.HelperWorkEvent(
        client_id=work_event.client_id,
        location_id=work_event.location_id,
        work_date=work_event.work_date,
        start_time=work_event.start_time,
        end_time=work_event.end_time,
        service_amount=(
            _money(Decimal(str(work_event.service_amount)))
            if work_event.service_amount is not None
            else None
        ),
        service_type=work_event.service_type,
        service_frequency=work_event.service_frequency,
        payment_method=work_event.payment_method,
        payment_status=payment_status,
        payment_received_date=payment_received_date,
        notes=(
            work_event.notes.strip()
            if work_event.notes
            else None
        ),
    )

    db.add(db_event)
    db.flush()

    created_entries = []

    # ---------------------------------------------------------
    # 6. Crear un HelperTimeEntry por cada helper
    # ---------------------------------------------------------
    for helper_item in work_event.helpers:
        work_minutes = helper_item.work_minutes

        if work_minutes is None:
            work_minutes = default_work_minutes

        db_time_entry = models.HelperTimeEntry(
            helper_id=helper_item.helper_id,
            work_event_id=db_event.id,

            # Campos duplicados temporalmente para mantener
            # compatibilidad con los flujos y listados actuales.
            client_id=work_event.client_id,
            work_date=work_event.work_date,
            start_time=work_event.start_time,
            end_time=work_event.end_time,

            helper_payroll_period_id=None,
            work_minutes=work_minutes,

            # El valor correcto será calculado después de guardar
            # todos los eventos del día.
            travel_minutes=0,

            notes=(
                helper_item.notes.strip()
                if helper_item.notes
                else None
            ),
        )

        db.add(db_time_entry)
        created_entries.append(db_time_entry)

    # ---------------------------------------------------------
    # 7. Guardar evento y participaciones
    # ---------------------------------------------------------
    db.commit()
    db.refresh(db_event)

    for entry in created_entries:
        db.refresh(entry)

    # ---------------------------------------------------------
    # 8. Recalcular Work Time y Travel Time del día completo
    # ---------------------------------------------------------
    affected_payroll_ids = set()

    for helper_id in helper_ids:
        recalculated_entries = (
            _recalculate_helper_time_entries_for_day(
                db=db,
                helper_id=helper_id,
                work_date=work_event.work_date,
            )
        )

        for entry in recalculated_entries:
            if entry.helper_payroll_period_id is not None:
                affected_payroll_ids.add(
                    entry.helper_payroll_period_id
                )

    # ---------------------------------------------------------
    # 9. Actualizar payrolls afectados
    # ---------------------------------------------------------
    for payroll_id in affected_payroll_ids:
        _recalculate_helper_payroll_period_totals(
            db=db,
            payroll_id=payroll_id,
        )

    # ---------------------------------------------------------
    # 10. Refrescar antes de responder
    # ---------------------------------------------------------
    db.refresh(db_event)

    for entry in created_entries:
        db.refresh(entry)

    return db_event


def get_helper_work_event(
    db: Session,
    work_event_id: int,
):
    return (
        db.query(models.HelperWorkEvent)
        .options(
            joinedload(models.HelperWorkEvent.time_entries)
        )
        .filter(
            models.HelperWorkEvent.id == work_event_id
        )
        .first()
    )


def update_helper_work_event(
    db: Session,
    work_event_id: int,
    work_event: schemas.HelperWorkEventUpdate,
):
    db_event = get_helper_work_event(
        db=db,
        work_event_id=work_event_id,
    )

    if not db_event:
        return None

    fields_set = work_event.model_fields_set

    # ---------------------------------------------------------
    # 1. Resolver valores efectivos del evento
    # ---------------------------------------------------------
    new_client_id = (
        work_event.client_id
        if "client_id" in fields_set
        else db_event.client_id
    )
    new_location_id = (
        work_event.location_id
        if "location_id" in fields_set
        else db_event.location_id
    )
    new_work_date = (
        work_event.work_date
        if "work_date" in fields_set
        else db_event.work_date
    )
    new_start_time = (
        work_event.start_time
        if "start_time" in fields_set
        else db_event.start_time
    )
    new_end_time = (
        work_event.end_time
        if "end_time" in fields_set
        else db_event.end_time
    )

    if (new_start_time is None) != (new_end_time is None):
        raise ValueError(
            "Start time and end time must both be provided or both be empty"
        )

    if (
        new_start_time is not None
        and new_end_time is not None
        and new_end_time <= new_start_time
    ):
        raise ValueError("End time must be after start time")

    # ---------------------------------------------------------
    # 2. Validar cliente y location efectivos
    # ---------------------------------------------------------
    client = get_client(db, new_client_id)

    if not client:
        raise ValueError("Client not found")

    if new_location_id is not None:
        location = (
            db.query(models.ClientLocation)
            .filter(
                models.ClientLocation.id == new_location_id,
                models.ClientLocation.client_id == new_client_id,
                models.ClientLocation.is_active.is_(True),
            )
            .first()
        )

        if not location:
            raise ValueError(
                "The selected location does not belong to the selected "
                "client or is inactive."
            )

    # ---------------------------------------------------------
    # 3. Validar helpers cuando se incluyan en el payload
    # ---------------------------------------------------------
    requested_helpers = work_event.helpers
    requested_helper_ids = None

    if "helpers" in fields_set:
        if not requested_helpers:
            raise ValueError("At least one helper is required")

        requested_helper_ids = {
            helper_item.helper_id
            for helper_item in requested_helpers
        }

        for helper_id in requested_helper_ids:
            helper = get_helper(db, helper_id)

            if not helper:
                raise ValueError(
                    f"Helper not found: {helper_id}"
                )

    # ---------------------------------------------------------
    # 4. Guardar valores anteriores para recalcular
    # ---------------------------------------------------------
    old_work_date = db_event.work_date
    old_helper_ids = {
        entry.helper_id
        for entry in db_event.time_entries
    }

    # ---------------------------------------------------------
    # 5. Actualizar campos del Work Event
    # ---------------------------------------------------------
    db_event.client_id = new_client_id
    db_event.location_id = new_location_id
    db_event.work_date = new_work_date
    db_event.start_time = new_start_time
    db_event.end_time = new_end_time

    if "service_amount" in fields_set:
        db_event.service_amount = (
            _money(Decimal(str(work_event.service_amount)))
            if work_event.service_amount is not None
            else None
        )

    if "service_type" in fields_set:
        db_event.service_type = work_event.service_type

    if "service_frequency" in fields_set:
        db_event.service_frequency = work_event.service_frequency

    if "payment_method" in fields_set:
        db_event.payment_method = work_event.payment_method

    if "notes" in fields_set:
        db_event.notes = (
            work_event.notes.strip()
            if work_event.notes
            else None
        )

    # ---------------------------------------------------------
    # 6. Normalizar estado y fecha de pago
    # ---------------------------------------------------------
    new_payment_status = (
        work_event.payment_status
        if "payment_status" in fields_set
        else db_event.payment_status
    ) or "Pending"

    if "payment_received_date" in fields_set:
        new_payment_received_date = work_event.payment_received_date
    else:
        new_payment_received_date = db_event.payment_received_date

    if new_payment_status == "Collected":
        if new_payment_received_date is None:
            new_payment_received_date = new_work_date
    elif new_payment_status == "Pending":
        new_payment_received_date = None

    db_event.payment_status = new_payment_status
    db_event.payment_received_date = new_payment_received_date

    # ---------------------------------------------------------
    # 7. Calcular minutos por defecto
    # ---------------------------------------------------------
    default_work_minutes = 0

    if new_start_time is not None and new_end_time is not None:
        default_work_minutes = _minutes_between(
            new_start_time,
            new_end_time,
        )

    existing_entries_by_helper = {
        entry.helper_id: entry
        for entry in db_event.time_entries
    }

    # ---------------------------------------------------------
    # 8. Actualizar la lista de helpers, si fue enviada
    # ---------------------------------------------------------
    if requested_helper_ids is not None:
        for helper_item in requested_helpers:
            helper_id = helper_item.helper_id
            work_minutes = helper_item.work_minutes

            if work_minutes is None:
                work_minutes = default_work_minutes

            existing_entry = existing_entries_by_helper.get(helper_id)

            if existing_entry:
                existing_entry.client_id = new_client_id
                existing_entry.work_date = new_work_date
                existing_entry.start_time = new_start_time
                existing_entry.end_time = new_end_time
                existing_entry.work_minutes = work_minutes
                existing_entry.notes = (
                    helper_item.notes.strip()
                    if helper_item.notes
                    else None
                )
            else:
                new_entry = models.HelperTimeEntry(
                    helper_id=helper_id,
                    work_event_id=db_event.id,
                    helper_payroll_period_id=None,
                    client_id=new_client_id,
                    work_date=new_work_date,
                    start_time=new_start_time,
                    end_time=new_end_time,
                    work_minutes=work_minutes,
                    travel_minutes=0,
                    notes=(
                        helper_item.notes.strip()
                        if helper_item.notes
                        else None
                    ),
                )
                db.add(new_entry)

        entries_to_remove = [
            entry
            for entry in db_event.time_entries
            if entry.helper_id not in requested_helper_ids
        ]

        for entry in entries_to_remove:
            if entry.helper_payroll_period_id is not None:
                raise ValueError(
                    f"Helper {entry.helper_id} cannot be removed because "
                    "the time entry is already assigned to a payroll period."
                )

            db.delete(entry)

        final_helper_ids = requested_helper_ids

    else:
        # Mantener helpers actuales, pero sincronizar los campos duplicados.
        for entry in db_event.time_entries:
            entry.client_id = new_client_id
            entry.work_date = new_work_date
            entry.start_time = new_start_time
            entry.end_time = new_end_time

            if (
                "start_time" in fields_set
                or "end_time" in fields_set
            ):
                entry.work_minutes = default_work_minutes

        final_helper_ids = old_helper_ids

    # ---------------------------------------------------------
    # 9. Guardar cambios
    # ---------------------------------------------------------
    db.commit()
    db.refresh(db_event)

    # ---------------------------------------------------------
    # 10. Recalcular días/helpers afectados
    # ---------------------------------------------------------
    affected_helper_ids = old_helper_ids | final_helper_ids
    affected_payroll_ids = set()

    for helper_id in affected_helper_ids:
        old_entries = _recalculate_helper_time_entries_for_day(
            db=db,
            helper_id=helper_id,
            work_date=old_work_date,
        )

        for entry in old_entries:
            if entry.helper_payroll_period_id is not None:
                affected_payroll_ids.add(
                    entry.helper_payroll_period_id
                )

        if new_work_date != old_work_date:
            new_entries = _recalculate_helper_time_entries_for_day(
                db=db,
                helper_id=helper_id,
                work_date=new_work_date,
            )

            for entry in new_entries:
                if entry.helper_payroll_period_id is not None:
                    affected_payroll_ids.add(
                        entry.helper_payroll_period_id
                    )

    # ---------------------------------------------------------
    # 11. Recalcular Payrolls afectados
    # ---------------------------------------------------------
    for payroll_id in affected_payroll_ids:
        _recalculate_helper_payroll_period_totals(
            db=db,
            payroll_id=payroll_id,
        )

    db.refresh(db_event)

    return db_event
