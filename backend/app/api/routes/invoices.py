import re
from datetime import datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Cartridge,
    CartridgeModel,
    Department,
    Employee,
    Invoice,
    InvoiceLine,
    InvoiceLineSlot,
    LegalEntity,
    Operation,
    Printer,
    PrinterRepair,
    ServiceProvider,
    User,
)
from app.models.enums import (
    CartridgeColor,
    CartridgeKind,
    CartridgeStatus,
    InvoiceLineKind,
    InvoiceStatus,
    OperationType,
    PrinterRepairStatus,
    PrinterStatus,
    ServiceResult,
)
from app.schemas.cartridge import OperationCreate
from app.schemas.invoice import (
    InvoiceApplyResult,
    InvoiceListItem,
    InvoiceLineSlotUpdate,
    InvoiceLineUpdate,
    InvoiceRead,
    InvoiceUpdate,
)
from app.services.cartridge_service import (
    STATUS_TITLES,
    create_cartridge,
    perform_operation,
)
from app.services.invoice_parser import (
    InvoiceParseError,
    normalize_code,
    parse_invoice_pdf,
    slug,
    vendor_for_cartridge,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

MAX_FILE_SIZE = 10 * 1024 * 1024

SERVICE_STATUS = {
    InvoiceLineKind.REFILL: CartridgeStatus.IN_REFILL,
    InvoiceLineKind.RESTORE: CartridgeStatus.IN_RESTORE,
}

INVOICE_LOADS = (
    selectinload(Invoice.service_provider),
    selectinload(Invoice.legal_entity),
    selectinload(Invoice.department).selectinload(Department.legal_entity),
    selectinload(Invoice.holder_employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Invoice.lines).selectinload(InvoiceLine.cartridge_model),
    selectinload(Invoice.lines)
    .selectinload(InvoiceLine.printer)
    .selectinload(Printer.model),
    selectinload(Invoice.lines)
    .selectinload(InvoiceLine.department)
    .selectinload(Department.legal_entity),
    selectinload(Invoice.lines)
    .selectinload(InvoiceLine.slots)
    .selectinload(InvoiceLineSlot.cartridge)
    .selectinload(Cartridge.model),
    selectinload(Invoice.lines)
    .selectinload(InvoiceLine.slots)
    .selectinload(InvoiceLineSlot.department)
    .selectinload(Department.legal_entity),
)


def _get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice).options(*INVOICE_LOADS).where(Invoice.id == invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    return invoice


def _org_name(raw: str) -> str:
    name = raw.strip()
    if re.match(r"^(ООО|ОАО|ЗАО|ПАО|АО|ИП)\b", name, re.IGNORECASE):
        return name
    return f"ООО «{name}»"


def _match_cartridge_model(
    models: list[CartridgeModel], target: str
) -> CartridgeModel | None:
    key = normalize_code(target).lower()
    if not key:
        return None
    exact = [m for m in models if normalize_code(m.name).lower() == key]
    if exact:
        return exact[0]
    partial = [m for m in models if key in normalize_code(m.name).lower()]
    return partial[0] if len(partial) == 1 else None


def _match_or_create_model(
    db: Session,
    invoice: Invoice,
    models: list[CartridgeModel],
    by_key: dict[str, CartridgeModel],
    target: str,
) -> CartridgeModel:
    key = normalize_code(target).lower()
    if key in by_key:
        return by_key[key]
    matched = _match_cartridge_model(models, target)
    if matched is not None:
        by_key[key] = matched
        return matched
    model = CartridgeModel(
        vendor=vendor_for_cartridge(target),
        name=target[:150],
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        refillable=True,
        notes=f"Создано автоматически из счёта № {invoice.number}",
    )
    db.add(model)
    db.flush()
    models.append(model)
    by_key[key] = model
    return model


def _fill_auto_matches(
    db: Session, invoice: Invoice, force: bool = False
) -> None:
    models = list(db.scalars(select(CartridgeModel)))
    by_key = {normalize_code(model.name).lower(): model for model in models}
    printers = list(
        db.scalars(select(Printer).options(selectinload(Printer.model)))
    )
    for line in invoice.lines:
        if line.skipped or line.applied:
            continue
        if line.kind == InvoiceLineKind.REPAIR:
            if line.printer_id is None:
                printer = _match_printer(printers, line.target_raw)
                if printer is not None:
                    line.printer_id = printer.id
                    line.printer = printer
            continue
        if line.cartridge_model_id is not None and not force:
            continue
        model = _match_or_create_model(db, invoice, models, by_key, line.target_raw)
        line.cartridge_model_id = model.id
        line.cartridge_model = model


def _match_printer(printers: list[Printer], target: str) -> Printer | None:
    key = target.lower()
    tokens = [t for t in re.split(r"[\s\-/]+", key) if len(t) > 1]

    def full_name(printer: Printer) -> str:
        return f"{printer.model.vendor} {printer.model.name}".lower()

    exact = [p for p in printers if full_name(p) == key]
    if exact:
        return exact[0]
    if not tokens:
        return None
    scored = []
    for printer in printers:
        name = full_name(printer)
        hits = sum(1 for token in tokens if token in name)
        if hits:
            scored.append((hits / len(tokens), printer))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= 0.75:
        return scored[0][1]
    return None


def _line_matched(line: InvoiceLine) -> bool:
    if line.kind == InvoiceLineKind.REPAIR:
        return line.printer_id is not None
    return line.cartridge_model_id is not None


def _counters(invoice: Invoice) -> tuple[int, int, int]:
    matched = applied = skipped = 0
    for line in invoice.lines:
        if line.skipped:
            skipped += 1
            continue
        if _line_matched(line):
            matched += 1
        if line.applied:
            applied += 1
    return matched, applied, skipped


def _to_read(db: Session, invoice: Invoice) -> InvoiceRead:
    payload = InvoiceRead.model_validate(invoice)
    matched, applied, skipped = _counters(invoice)
    payload.matched_lines = matched
    payload.applied_lines = applied
    payload.skipped_lines = skipped
    return payload


def _to_list_item(invoice: Invoice) -> InvoiceListItem:
    matched, applied, _ = _counters(invoice)
    item = InvoiceListItem.model_validate(invoice)
    item.lines_total = len(invoice.lines)
    item.lines_matched = matched
    item.lines_applied = applied
    return item


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceRead:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Ожидается файл в формате PDF")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пуст")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл больше 10 МБ")

    try:
        parsed = parse_invoice_pdf(data)
    except InvoiceParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if parsed.problems:
        raise HTTPException(status_code=400, detail="; ".join(parsed.problems))

    existing = db.scalar(
        select(Invoice).where(
            Invoice.number == parsed.number, Invoice.issued_at == parsed.issued_at
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Счёт № {parsed.number} от {parsed.issued_at:%d.%m.%Y} "
                f"уже загружен (id={existing.id})"
            ),
        )

    provider = None
    if parsed.supplier_inn:
        provider = db.scalar(
            select(ServiceProvider).where(
                ServiceProvider.inn == parsed.supplier_inn
            )
        )
    legal_entity = None
    if parsed.buyer_inn:
        legal_entity = db.scalar(
            select(LegalEntity).where(LegalEntity.inn == parsed.buyer_inn)
        )
    department = None
    if legal_entity is not None:
        department = db.scalar(
            select(Department)
            .where(
                Department.legal_entity_id == legal_entity.id,
                Department.is_active.is_(True),
            )
            .order_by(Department.id)
        )

    invoice = Invoice(
        number=parsed.number,
        issued_at=parsed.issued_at,
        supplier_name=parsed.supplier_name,
        supplier_inn=parsed.supplier_inn or None,
        service_provider_id=provider.id if provider else None,
        buyer_name=parsed.buyer_name,
        buyer_inn=parsed.buyer_inn or None,
        legal_entity_id=legal_entity.id if legal_entity else None,
        department_id=department.id if department else None,
        total=parsed.total,
        vat=parsed.vat,
        vat_rate=parsed.vat_rate,
        cost_with_vat=False,
        file_name=filename[:255],
        status=InvoiceStatus.DRAFT,
        created_by_id=current_user.id,
    )

    for parsed_line in parsed.lines:
        line = InvoiceLine(
            number=parsed_line.number,
            title=parsed_line.title,
            kind=parsed_line.kind,
            target_raw=parsed_line.target_raw,
            qty=parsed_line.qty,
            price=parsed_line.price,
            total=parsed_line.total,
        )
        line.slots = [
            InvoiceLineSlot(position=index)
            for index in range(1, parsed_line.qty + 1)
        ]
        invoice.lines.append(line)

    db.add(invoice)
    db.flush()
    _fill_auto_matches(db, invoice)
    db.commit()
    return _to_read(db, _get_invoice(db, invoice.id))


@router.get("", response_model=list[InvoiceListItem])
def list_invoices(
    status_filter: InvoiceStatus | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[InvoiceListItem]:
    stmt = select(Invoice).options(selectinload(Invoice.lines))
    if status_filter is not None:
        stmt = stmt.where(Invoice.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Invoice.number.ilike(pattern),
                Invoice.supplier_name.ilike(pattern),
                Invoice.buyer_name.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Invoice.issued_at.desc(), Invoice.id.desc()).limit(200)
    return [_to_list_item(invoice) for invoice in db.scalars(stmt)]


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceRead:
    return _to_read(db, _get_invoice(db, invoice_id))


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(
            status_code=409, detail="Проведённый счёт нельзя изменить"
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "service_provider_id" and value is not None:
            if db.get(ServiceProvider, value) is None:
                raise HTTPException(
                    status_code=404, detail="Сервисная организация не найдена"
                )
        if field == "legal_entity_id" and value is not None:
            if db.get(LegalEntity, value) is None:
                raise HTTPException(status_code=404, detail="Юрлицо не найдено")
        if field == "department_id" and value is not None:
            if db.get(Department, value) is None:
                raise HTTPException(
                    status_code=404, detail="Подразделение не найдено"
                )
        if field == "holder_employee_id" and value is not None:
            if db.get(Employee, value) is None:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
        setattr(invoice, field, value)

    db.commit()
    db.expire_all()
    return _to_read(db, _get_invoice(db, invoice_id))


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceRead)
def update_line(
    invoice_id: int,
    line_id: int,
    data: InvoiceLineUpdate,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(
            status_code=409, detail="Проведённый счёт нельзя изменить"
        )
    line = next((item for item in invoice.lines if item.id == line_id), None)
    if line is None:
        raise HTTPException(status_code=404, detail="Позиция счёта не найдена")
    if line.applied:
        raise HTTPException(status_code=409, detail="Позиция уже проведена")

    changes = data.model_dump(exclude_unset=True)

    if "skipped" in changes:
        line.skipped = bool(changes["skipped"])

    if "cartridge_model_id" in changes:
        if line.kind == InvoiceLineKind.REPAIR:
            raise HTTPException(
                status_code=400, detail="Для ремонта укажите принтер, а не модель картриджа"
            )
        model_id = changes["cartridge_model_id"]
        model = None
        if model_id is not None:
            model = db.get(CartridgeModel, model_id)
            if model is None:
                raise HTTPException(
                    status_code=404, detail="Модель картриджа не найдена"
                )
        line.cartridge_model_id = model_id
        line.cartridge_model = model
        for slot in line.slots:
            slot.cartridge_id = None
            slot.cartridge = None

    if "printer_id" in changes:
        if line.kind != InvoiceLineKind.REPAIR:
            raise HTTPException(
                status_code=400, detail="Принтер указывается только для ремонта"
            )
        printer_id = changes["printer_id"]
        printer = None
        if printer_id is not None:
            printer = db.get(Printer, printer_id)
            if printer is None:
                raise HTTPException(status_code=404, detail="Принтер не найден")
        line.printer_id = printer_id
        line.printer = printer

    if "department_id" in changes:
        department_id = changes["department_id"]
        department = _resolve_department_choice(db, invoice, department_id)
        line.department_id = department_id
        line.department = department

    db.commit()
    db.expire_all()
    return _to_read(db, _get_invoice(db, invoice_id))


@router.patch(
    "/{invoice_id}/lines/{line_id}/slots/{slot_id}", response_model=InvoiceRead
)
def update_slot(
    invoice_id: int,
    line_id: int,
    slot_id: int,
    data: InvoiceLineSlotUpdate,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(
            status_code=409, detail="Проведённый счёт нельзя изменить"
        )
    line = next((item for item in invoice.lines if item.id == line_id), None)
    if line is None:
        raise HTTPException(status_code=404, detail="Позиция счёта не найдена")
    if line.applied:
        raise HTTPException(status_code=409, detail="Позиция уже проведена")
    if line.kind == InvoiceLineKind.REPAIR:
        raise HTTPException(
            status_code=400, detail="Для ремонта картриджи не сопоставляются"
        )
    slot = next((item for item in line.slots if item.id == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Картридж позиции не найден")

    changes = data.model_dump(exclude_unset=True)

    if "cartridge_id" in changes:
        cartridge_id = changes["cartridge_id"]
        cartridge = None
        if cartridge_id is not None:
            cartridge = db.get(Cartridge, cartridge_id)
            if cartridge is None:
                raise HTTPException(status_code=404, detail="Картридж не найден")
            if line.cartridge_model_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Позиция {line.number}: сначала выберите модель картриджа"
                    ),
                )
            if cartridge.model_id != line.cartridge_model_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Картридж {cartridge.inventory_no} относится к другой модели"
                    ),
                )
            if cartridge.status not in _allowed_statuses(line.kind):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Картридж {cartridge.inventory_no} нельзя использовать: "
                        f"он {STATUS_TITLES[cartridge.status]}"
                    ),
                )
            if any(
                other.id != slot.id and other.cartridge_id == cartridge_id
                for other in line.slots
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Этот картридж уже выбран в другой строке позиции"
                    ),
                )
        slot.cartridge_id = cartridge_id
        slot.cartridge = cartridge

    if "department_id" in changes:
        department_id = changes["department_id"]
        department = _resolve_department_choice(db, invoice, department_id)
        slot.department_id = department_id
        slot.department = department

    db.commit()
    db.expire_all()
    return _to_read(db, _get_invoice(db, invoice_id))


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)) -> None:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(
            status_code=409, detail="Проведённый счёт нельзя удалить"
        )
    db.delete(invoice)
    db.commit()


def _ensure_provider(db: Session, invoice: Invoice) -> ServiceProvider:
    if invoice.service_provider_id:
        provider = db.get(ServiceProvider, invoice.service_provider_id)
        if provider is not None:
            return provider
    if invoice.supplier_inn:
        provider = db.scalar(
            select(ServiceProvider).where(ServiceProvider.inn == invoice.supplier_inn)
        )
        if provider is not None:
            return provider
    provider = ServiceProvider(
        name=_org_name(invoice.supplier_name),
        inn=invoice.supplier_inn,
        notes=f"Создано при импорте счёта № {invoice.number}",
    )
    db.add(provider)
    db.flush()
    return provider


def _ensure_ownership(
    db: Session, invoice: Invoice
) -> tuple[LegalEntity, Department, Employee]:
    legal_entity = (
        db.get(LegalEntity, invoice.legal_entity_id)
        if invoice.legal_entity_id
        else None
    )
    if legal_entity is None and invoice.buyer_inn:
        legal_entity = db.scalar(
            select(LegalEntity).where(LegalEntity.inn == invoice.buyer_inn)
        )
    if legal_entity is None:
        legal_entity = LegalEntity(
            name=_org_name(invoice.buyer_name),
            inn=invoice.buyer_inn,
            notes=f"Создано при импорте счёта № {invoice.number}",
        )
        db.add(legal_entity)
        db.flush()

    department = (
        db.get(Department, invoice.department_id) if invoice.department_id else None
    )
    if department is None:
        department = db.scalar(
            select(Department)
            .where(
                Department.legal_entity_id == legal_entity.id,
                Department.is_active.is_(True),
            )
            .order_by(Department.id)
        )
    if department is None:
        department = Department(
            legal_entity_id=legal_entity.id,
            name="Основной отдел",
        )
        db.add(department)
        db.flush()

    holder = (
        db.get(Employee, invoice.holder_employee_id)
        if invoice.holder_employee_id
        else None
    )
    if holder is None:
        holder = db.scalar(
            select(Employee).where(
                Employee.department_id == department.id,
                Employee.is_active.is_(True),
            )
        )
    if holder is None:
        holder = Employee(
            full_name="Ответственный за оргтехнику",
            department_id=department.id,
            position="Ответственный за оргтехнику",
        )
        db.add(holder)
        db.flush()

    return legal_entity, department, holder


def _next_inventory_no(db: Session, model: CartridgeModel) -> str:
    base = slug(model.name)[:44]
    used = set(
        db.scalars(
            select(Cartridge.inventory_no).where(
                Cartridge.inventory_no.like(f"{base}-%")
            )
        )
    )
    seq = 1
    while f"{base}-{seq:03d}" in used:
        seq += 1
    return f"{base}-{seq:03d}"


def _allowed_statuses(kind: InvoiceLineKind) -> set[CartridgeStatus]:
    allowed = {CartridgeStatus.IN_STOCK}
    service_status = SERVICE_STATUS.get(kind)
    if service_status is not None:
        allowed.add(service_status)
    return allowed


def _department_or_default(
    db: Session, department_id: int | None, fallback: Department
) -> Department:
    if department_id:
        department = db.get(Department, department_id)
        if department is not None:
            return department
    return fallback


def _resolve_department_choice(
    db: Session, invoice: Invoice, department_id: int | None
) -> Department | None:
    if department_id is None:
        return None
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")
    if (
        invoice.legal_entity_id is not None
        and department.legal_entity_id != invoice.legal_entity_id
    ):
        raise HTTPException(
            status_code=400, detail="Подразделение относится к другому юрлицу"
        )
    if invoice.legal_entity_id is None:
        invoice.legal_entity_id = department.legal_entity_id
    return department


def _candidate_cartridges(
    db: Session,
    model: CartridgeModel,
    kind: InvoiceLineKind,
    provider: ServiceProvider,
    exclude: set[int],
) -> list[Cartridge]:
    service_status = SERVICE_STATUS.get(kind)
    allowed = _allowed_statuses(kind)
    rows = db.scalars(
        select(Cartridge).where(
            Cartridge.model_id == model.id,
            Cartridge.status.in_(allowed),
        )
    ).all()

    def rank(cartridge: Cartridge) -> int:
        if service_status is not None and cartridge.status == service_status:
            return 0 if cartridge.service_provider_id == provider.id else 2
        return 1

    return [
        cartridge
        for cartridge in sorted(rows, key=lambda item: (rank(item), item.id))
        if cartridge.id not in exclude
    ]


def _net_amount(amount: Decimal, vat_rate: Decimal) -> Decimal:
    if not vat_rate:
        return amount
    factor = Decimal(1) + vat_rate / Decimal(100)
    return (amount / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _operation_cost(invoice: Invoice, amount: Decimal) -> Decimal:
    if invoice.cost_with_vat:
        return amount
    return _net_amount(amount, invoice.vat_rate)


def _line_costs(invoice: Invoice, line: InvoiceLine) -> list[Decimal]:
    """Стоимость каждой единицы позиции; сумма точно равна сумме строки."""
    total = (
        line.total
        if invoice.cost_with_vat
        else _net_amount(line.total, invoice.vat_rate)
    )
    qty = max(1, line.qty)
    base = (total / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    costs = [base] * (qty - 1)
    costs.append(total - base * (qty - 1))
    return costs


def _apply_repair(
    db: Session,
    invoice: Invoice,
    line: InvoiceLine,
    provider: ServiceProvider,
    department: Department,
    legal_entity: LegalEntity,
    user: User,
    sent_at: datetime,
    done_at: datetime,
) -> PrinterRepair:
    printer = db.get(Printer, line.printer_id)
    if printer is None:
        raise HTTPException(
            status_code=400, detail=f"Позиция {line.number}: принтер не найден"
        )
    if printer.status == PrinterStatus.RETIRED:
        raise HTTPException(
            status_code=409,
            detail=f"Принтер {printer.inventory_no} списан, ремонт невозможен",
        )
    open_repair = db.scalar(
        select(PrinterRepair).where(
            PrinterRepair.printer_id == printer.id,
            PrinterRepair.status == PrinterRepairStatus.IN_SERVICE.value,
        )
    )
    if open_repair is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Принтер {printer.inventory_no} уже находится в ремонте",
        )

    repair = PrinterRepair(
        printer_id=printer.id,
        service_provider_id=provider.id,
        status=PrinterRepairStatus.RETURNED.value,
        sent_at=sent_at,
        expected_return_date=invoice.issued_at,
        returned_at=done_at,
        document_no=f"Счёт № {invoice.number}",
        comment=f"Импорт счёта № {invoice.number}, позиция {line.number}",
        result=ServiceResult.REPAIRED.value,
        cost=_operation_cost(invoice, line.total),
        legal_entity_id=legal_entity.id,
        department_id=department.id,
        user_id=user.id,
    )
    db.add(repair)
    printer.status = PrinterStatus.ACTIVE
    printer.service_provider_id = None
    printer.service_since = None
    printer.expected_return_date = None
    return repair


@router.post("/{invoice_id}/auto-match", response_model=InvoiceRead)
def auto_match_invoice(
    invoice_id: int, db: Session = Depends(get_db)
) -> InvoiceRead:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(
            status_code=409, detail="Проведённый счёт нельзя изменить"
        )
    _fill_auto_matches(db, invoice)
    db.commit()
    db.expire_all()
    return _to_read(db, _get_invoice(db, invoice_id))


@router.post("/{invoice_id}/unapply", response_model=InvoiceRead)
def unapply_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceRead:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status != InvoiceStatus.APPLIED:
        raise HTTPException(status_code=409, detail="Счёт не проведён")

    document_no = f"Счёт № {invoice.number}"
    operations = list(
        db.scalars(select(Operation).where(Operation.document_no == document_no))
    )
    repairs = list(
        db.scalars(
            select(PrinterRepair).where(PrinterRepair.document_no == document_no)
        )
    )

    by_cartridge: dict[int, list[Operation]] = {}
    for operation in operations:
        by_cartridge.setdefault(operation.cartridge_id, []).append(operation)

    blocked: list[str] = []
    for cartridge_id, cartridge_operations in by_cartridge.items():
        last_id = max(item.id for item in cartridge_operations)
        later = db.scalar(
            select(Operation.id)
            .where(
                Operation.cartridge_id == cartridge_id,
                Operation.id > last_id,
            )
            .limit(1)
        )
        if later is not None:
            cartridge = db.get(Cartridge, cartridge_id)
            blocked.append(
                cartridge.inventory_no if cartridge else str(cartridge_id)
            )
    if blocked:
        raise HTTPException(
            status_code=409,
            detail=(
                "Отмена невозможна: по картриджам уже есть более поздние "
                "операции — " + ", ".join(blocked)
            ),
        )

    created_ids = set(
        db.scalars(
            select(Cartridge.id).where(
                Cartridge.notes == f"Создано при импорте счёта № {invoice.number}"
            )
        )
    )

    for cartridge_id, cartridge_operations in by_cartridge.items():
        cartridge = db.get(Cartridge, cartridge_id)
        first = min(cartridge_operations, key=lambda item: item.id)
        refill_done = sum(
            1
            for item in cartridge_operations
            if item.type == OperationType.REFILL_DONE
        )
        for operation in sorted(
            cartridge_operations, key=lambda item: item.id, reverse=True
        ):
            db.delete(operation)
        if cartridge is None:
            continue
        cartridge.refill_count = max(0, cartridge.refill_count - refill_done)
        if first.from_status is not None:
            cartridge.status = first.from_status
        if cartridge.status == CartridgeStatus.IN_STOCK:
            cartridge.service_provider_id = None
            cartridge.service_since = None
            cartridge.expected_return_date = None
        else:
            cartridge.service_provider_id = first.service_provider_id
            cartridge.service_since = first.occurred_at
    db.flush()

    for repair in repairs:
        db.delete(repair)
    db.flush()

    for cartridge_id in created_ids:
        cartridge = db.get(Cartridge, cartridge_id)
        if cartridge is None:
            continue
        other_operations = db.scalar(
            select(func.count())
            .select_from(Operation)
            .where(
                Operation.cartridge_id == cartridge_id,
                Operation.type != OperationType.RECEIPT,
            )
        )
        if other_operations:
            continue
        db.delete(cartridge)
    db.flush()

    for line in invoice.lines:
        line.applied = False
        line.applied_note = None
        for slot in line.slots:
            slot.applied = False
            if slot.cartridge_id in created_ids:
                slot.cartridge_id = None
                slot.cartridge = None

    invoice.status = InvoiceStatus.DRAFT
    invoice.applied_at = None
    db.commit()
    db.expire_all()
    return _to_read(db, _get_invoice(db, invoice_id))


@router.post("/{invoice_id}/apply", response_model=InvoiceApplyResult)
def apply_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceApplyResult:
    invoice = _get_invoice(db, invoice_id)
    if invoice.status == InvoiceStatus.APPLIED:
        raise HTTPException(status_code=409, detail="Счёт уже проведён")

    pending = [
        line for line in invoice.lines if not line.skipped and not line.applied
    ]
    if not pending:
        raise HTTPException(status_code=400, detail="Нет позиций для проведения")
    unmatched = [line.number for line in pending if not _line_matched(line)]
    if unmatched:
        raise HTTPException(
            status_code=400,
            detail="Не сопоставлены позиции: "
            + ", ".join(str(number) for number in unmatched),
        )

    provider = _ensure_provider(db, invoice)
    legal_entity, department, holder = _ensure_ownership(db, invoice)
    invoice.service_provider_id = provider.id
    invoice.legal_entity_id = legal_entity.id
    invoice.department_id = department.id
    invoice.holder_employee_id = holder.id

    sent_at = datetime.combine(
        invoice.issued_at - timedelta(days=invoice.sent_offset_days), time(12)
    ).astimezone()
    done_at = datetime.combine(invoice.issued_at, time(12)).astimezone()
    document_no = f"Счёт № {invoice.number}"

    operations_created = 0
    repairs_created = 0
    cartridges_created = 0
    posted_cost = Decimal("0")

    for line in pending:
        if line.kind == InvoiceLineKind.REPAIR:
            _apply_repair(
                db, invoice, line, provider, department, legal_entity,
                current_user, sent_at, done_at,
            )
            repairs_created += 1
            posted_cost += _operation_cost(invoice, line.total)
            line.applied = True
            line.applied_note = "Ремонт принтера"
            continue

        model = db.get(CartridgeModel, line.cartridge_model_id)
        if model is None:
            raise HTTPException(
                status_code=400,
                detail=f"Позиция {line.number}: не найдена модель картриджа",
            )
        if line.kind == InvoiceLineKind.REFILL and not model.refillable:
            raise HTTPException(
                status_code=400,
                detail=f"Позиция {line.number}: модель {model.name} не подлежит заправке",
            )

        db.flush()
        slots = sorted(line.slots, key=lambda item: item.position)
        while len(slots) < line.qty:
            extra = InvoiceLineSlot(line=line, position=len(slots) + 1)
            db.add(extra)
            slots.append(extra)

        used = {slot.cartridge_id for slot in slots if slot.cartridge_id}
        candidates = _candidate_cartridges(db, model, line.kind, provider, used)
        resolved: list[tuple[InvoiceLineSlot, Cartridge, Department]] = []
        for slot in slots:
            cartridge = (
                db.get(Cartridge, slot.cartridge_id) if slot.cartridge_id else None
            )
            if cartridge is None and candidates:
                cartridge = candidates.pop(0)
            if cartridge is None:
                cartridge = create_cartridge(
                    db,
                    inventory_no=_next_inventory_no(db, model),
                    serial_no=None,
                    model_id=model.id,
                    purchase_price=None,
                    purchase_date=None,
                    notes=f"Создано при импорте счёта № {invoice.number}",
                    comment=f"{invoice.number} · позиция {line.number}",
                    user_id=current_user.id,
                )
                cartridges_created += 1
            slot.cartridge_id = cartridge.id
            slot.cartridge = cartridge
            slot_department = _department_or_default(
                db, slot.department_id or line.department_id, department
            )
            resolved.append((slot, cartridge, slot_department))

        service_status = SERVICE_STATUS[line.kind]
        send_type = (
            OperationType.SEND_RESTORE
            if line.kind == InvoiceLineKind.RESTORE
            else OperationType.SEND_REFILL
        )
        done_type = (
            OperationType.RESTORE_DONE
            if line.kind == InvoiceLineKind.RESTORE
            else OperationType.REFILL_DONE
        )
        comment = f"{document_no}, позиция {line.number}"
        costs = _line_costs(invoice, line)
        closed_from_service = 0
        for index, (slot, cartridge, slot_department) in enumerate(resolved):
            unit_cost = costs[index] if index < len(costs) else costs[-1]
            if cartridge.department_id is None:
                cartridge.department_id = slot_department.id
                cartridge.legal_entity_id = slot_department.legal_entity_id
            if cartridge.status == service_status:
                perform_operation(
                    db,
                    cartridge,
                    OperationCreate(
                        type=done_type,
                        service_provider_id=provider.id,
                        cost=unit_cost,
                        document_no=document_no,
                        comment=comment,
                        occurred_at=done_at,
                    ),
                    current_user.id,
                )
                operations_created += 1
                posted_cost += unit_cost
                closed_from_service += 1
            else:
                perform_operation(
                    db,
                    cartridge,
                    OperationCreate(
                        type=send_type,
                        service_provider_id=provider.id,
                        expected_return_date=invoice.issued_at,
                        document_no=document_no,
                        comment=comment,
                        occurred_at=sent_at,
                    ),
                    current_user.id,
                )
                perform_operation(
                    db,
                    cartridge,
                    OperationCreate(
                        type=done_type,
                        service_provider_id=provider.id,
                        cost=unit_cost,
                        document_no=document_no,
                        comment=comment,
                        occurred_at=done_at,
                    ),
                    current_user.id,
                )
                operations_created += 2
                posted_cost += unit_cost
            slot.applied = True

        line.applied = True
        note = (
            f"{'Восстановление' if line.kind == InvoiceLineKind.RESTORE else 'Заправка'}: "
            + ", ".join(cartridge.inventory_no for _, cartridge, _ in resolved)
        )
        if closed_from_service:
            note += f"; закрыто после обслуживания: {closed_from_service}"
        line.applied_note = note

    invoice.status = InvoiceStatus.APPLIED
    invoice.applied_at = datetime.now().astimezone()
    db.commit()

    skipped_lines = sum(1 for line in invoice.lines if line.skipped)
    return InvoiceApplyResult(
        operations_created=operations_created,
        repairs_created=repairs_created,
        cartridges_created=cartridges_created,
        applied_lines=len(pending),
        skipped_lines=skipped_lines,
        posted_cost=posted_cost,
    )
