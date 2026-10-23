from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Cartridge,
    Department,
    Employee,
    Operation,
    Printer,
    PrinterModel,
    PrinterRepair,
    ServiceProvider,
    User,
)
from app.models.enums import (
    PrinterRepairStatus,
    PrinterStatus,
    ServiceResult,
)
from app.schemas.printer import PrinterCreate, PrinterRead, PrinterUpdate
from app.schemas.printer_repair import (
    PrinterRepairClose,
    PrinterRepairCreate,
    PrinterRepairRead,
)

router = APIRouter(prefix="/printers", tags=["printers"])

PRINTER_LOADS = (
    selectinload(Printer.model),
    selectinload(Printer.department).selectinload(Department.legal_entity),
    selectinload(Printer.employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Printer.service_provider),
)

REPAIR_LOADS = (
    selectinload(PrinterRepair.service_provider),
    selectinload(PrinterRepair.legal_entity),
    selectinload(PrinterRepair.department).selectinload(Department.legal_entity),
    selectinload(PrinterRepair.user),
)

OPEN_REPAIR_STATUS = PrinterRepairStatus.IN_SERVICE.value


def _get_printer(db: Session, printer_id: int) -> Printer:
    printer = db.scalar(
        select(Printer).options(*PRINTER_LOADS).where(Printer.id == printer_id)
    )
    if printer is None:
        raise HTTPException(status_code=404, detail="Принтер не найден")
    return printer


def _get_repair(db: Session, repair_id: int) -> PrinterRepair:
    repair = db.scalar(
        select(PrinterRepair)
        .options(*REPAIR_LOADS)
        .where(PrinterRepair.id == repair_id)
    )
    if repair is None:
        raise HTTPException(status_code=404, detail="Запись о ремонте не найдена")
    return repair


def _get_provider(db: Session, provider_id: int) -> ServiceProvider:
    provider = db.get(ServiceProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Сервисная организация не найдена")
    if not provider.is_active:
        raise HTTPException(
            status_code=409, detail="Сервисная организация деактивирована"
        )
    return provider


def _has_open_repair(db: Session, printer_id: int) -> bool:
    return bool(
        db.scalar(
            select(PrinterRepair.id)
            .where(
                PrinterRepair.printer_id == printer_id,
                PrinterRepair.status == OPEN_REPAIR_STATUS,
            )
            .limit(1)
        )
    )


def _validate_refs(
    db: Session,
    model_id: int | None,
    employee_id: int | None,
    department_id: int | None = None,
) -> None:
    if model_id is not None and db.get(PrinterModel, model_id) is None:
        raise HTTPException(status_code=404, detail="Модель принтера не найдена")
    if employee_id is not None and db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status_code=404, detail="Отдел не найден")


@router.get("", response_model=list[PrinterRead])
def list_printers(
    q: str | None = None,
    status_filter: PrinterStatus | None = Query(default=None, alias="status"),
    employee_id: int | None = None,
    department_id: int | None = None,
    legal_entity_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[Printer]:
    stmt = select(Printer).options(*PRINTER_LOADS)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.join(Printer.model).where(
            or_(
                Printer.inventory_no.ilike(pattern),
                Printer.serial_no.ilike(pattern),
                Printer.location.ilike(pattern),
                PrinterModel.name.ilike(pattern),
                PrinterModel.vendor.ilike(pattern),
            )
        )
    if status_filter is not None:
        stmt = stmt.where(Printer.status == status_filter)
    if employee_id is not None:
        stmt = stmt.where(Printer.employee_id == employee_id)
    if department_id is not None:
        stmt = stmt.where(Printer.department_id == department_id)
    if legal_entity_id is not None:
        stmt = stmt.join(Printer.department).where(
            Department.legal_entity_id == legal_entity_id
        )
    stmt = stmt.order_by(Printer.inventory_no)
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=PrinterRead, status_code=status.HTTP_201_CREATED)
def create_printer(data: PrinterCreate, db: Session = Depends(get_db)) -> Printer:
    _validate_refs(db, data.model_id, data.employee_id, data.department_id)
    printer = Printer(**data.model_dump())
    db.add(printer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Принтер с таким инвентарным номером уже существует",
        ) from exc
    return _get_printer(db, printer.id)


@router.get("/{printer_id}", response_model=PrinterRead)
def get_printer(printer_id: int, db: Session = Depends(get_db)) -> Printer:
    return _get_printer(db, printer_id)


@router.patch("/{printer_id}", response_model=PrinterRead)
def update_printer(
    printer_id: int, data: PrinterUpdate, db: Session = Depends(get_db)
) -> Printer:
    printer = _get_printer(db, printer_id)
    payload = data.model_dump(exclude_unset=True)
    new_status = payload.get("status")
    if (
        new_status is not None
        and new_status != PrinterStatus.REPAIR
        and _has_open_repair(db, printer_id)
    ):
        raise HTTPException(
            status_code=409,
            detail="У принтера есть открытый ремонт. Сначала оформите возврат.",
        )
    _validate_refs(
        db,
        payload.get("model_id", printer.model_id),
        payload.get("employee_id", printer.employee_id),
        payload.get("department_id", printer.department_id),
    )
    for field, value in payload.items():
        setattr(printer, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Принтер с таким инвентарным номером уже существует",
        ) from exc
    db.expire(printer)
    return _get_printer(db, printer_id)


@router.delete("/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_printer(printer_id: int, db: Session = Depends(get_db)) -> Response:
    printer = _get_printer(db, printer_id)
    in_use = (
        db.scalar(
            select(func.count(Cartridge.id)).where(Cartridge.printer_id == printer_id)
        )
        or db.scalar(
            select(func.count(Operation.id)).where(Operation.printer_id == printer_id)
        )
        or db.scalar(
            select(func.count(PrinterRepair.id)).where(
                PrinterRepair.printer_id == printer_id
            )
        )
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Принтер используется в учёте и не может быть удалён",
        )
    db.delete(printer)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{printer_id}/repairs", response_model=list[PrinterRepairRead])
def list_printer_repairs(
    printer_id: int, db: Session = Depends(get_db)
) -> list[PrinterRepair]:
    _get_printer(db, printer_id)
    repairs = db.scalars(
        select(PrinterRepair)
        .options(*REPAIR_LOADS)
        .where(PrinterRepair.printer_id == printer_id)
        .order_by(PrinterRepair.sent_at.desc(), PrinterRepair.id.desc())
    ).all()
    return list(repairs)


@router.post(
    "/{printer_id}/repairs",
    response_model=PrinterRepairRead,
    status_code=status.HTTP_201_CREATED,
)
def send_printer_to_repair(
    printer_id: int,
    data: PrinterRepairCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PrinterRepair:
    printer = _get_printer(db, printer_id)
    if printer.status == PrinterStatus.RETIRED:
        raise HTTPException(
            status_code=409, detail="Списанный принтер нельзя отправить в ремонт"
        )
    if _has_open_repair(db, printer_id):
        raise HTTPException(
            status_code=409, detail="Принтер уже находится в ремонте"
        )
    provider = _get_provider(db, data.service_provider_id)

    sent_at = (
        data.sent_at.astimezone(timezone.utc)
        if data.sent_at is not None
        else datetime.now(timezone.utc)
    )
    department = printer.department or (
        printer.employee.department if printer.employee else None
    )

    repair = PrinterRepair(
        printer_id=printer.id,
        service_provider_id=provider.id,
        status=OPEN_REPAIR_STATUS,
        sent_at=sent_at,
        expected_return_date=data.expected_return_date,
        document_no=data.document_no,
        comment=data.comment,
        legal_entity_id=(
            department.legal_entity_id if department is not None else None
        ),
        department_id=department.id if department is not None else None,
        user_id=current_user.id,
    )
    db.add(repair)

    printer.status = PrinterStatus.REPAIR
    printer.service_provider_id = provider.id
    printer.service_since = sent_at
    printer.expected_return_date = data.expected_return_date

    db.commit()
    return _get_repair(db, repair.id)


@router.post(
    "/{printer_id}/repairs/{repair_id}/close",
    response_model=PrinterRepairRead,
)
def close_printer_repair(
    printer_id: int,
    repair_id: int,
    data: PrinterRepairClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PrinterRepair:
    printer = _get_printer(db, printer_id)
    repair = _get_repair(db, repair_id)
    if repair.printer_id != printer.id:
        raise HTTPException(status_code=404, detail="Запись о ремонте не найдена")
    if repair.status != OPEN_REPAIR_STATUS:
        raise HTTPException(status_code=409, detail="Ремонт уже завершён")

    returned_at = (
        data.returned_at.astimezone(timezone.utc)
        if data.returned_at is not None
        else datetime.now(timezone.utc)
    )
    repair.status = PrinterRepairStatus.RETURNED.value
    repair.returned_at = returned_at
    repair.cost = data.cost
    repair.result = data.result.value
    if data.document_no:
        repair.document_no = data.document_no
    if data.comment:
        repair.comment = data.comment
    repair.user_id = repair.user_id or current_user.id

    printer.service_provider_id = None
    printer.service_since = None
    printer.expected_return_date = None
    printer.status = (
        PrinterStatus.ACTIVE
        if data.result == ServiceResult.REPAIRED
        else PrinterStatus.REPAIR
    )

    db.commit()
    return _get_repair(db, repair.id)
