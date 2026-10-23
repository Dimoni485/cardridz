from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cartridge, Employee, Operation, Printer, ServiceProvider
from app.models.enums import (
    CartridgeStatus,
    OperationType,
    PrinterStatus,
    ServiceResult,
)
from app.schemas.cartridge import OperationCreate


class TransitionRule:
    def __init__(
        self,
        allowed_from: set[CartridgeStatus],
        to: CartridgeStatus,
        title: str,
    ) -> None:
        self.allowed_from = allowed_from
        self.to = to
        self.title = title


TRANSITIONS: dict[OperationType, TransitionRule] = {
    OperationType.ISSUE: TransitionRule(
        {CartridgeStatus.IN_STOCK}, CartridgeStatus.ISSUED, "Выдать сотруднику"
    ),
    OperationType.INSTALL: TransitionRule(
        {CartridgeStatus.IN_STOCK, CartridgeStatus.ISSUED},
        CartridgeStatus.INSTALLED,
        "Установить в принтер",
    ),
    OperationType.UNINSTALL: TransitionRule(
        {CartridgeStatus.INSTALLED}, CartridgeStatus.IN_STOCK, "Снять с принтера"
    ),
    OperationType.RETURN: TransitionRule(
        {CartridgeStatus.ISSUED}, CartridgeStatus.IN_STOCK, "Вернуть на склад"
    ),
    OperationType.SEND_REFILL: TransitionRule(
        {CartridgeStatus.IN_STOCK, CartridgeStatus.ISSUED},
        CartridgeStatus.IN_REFILL,
        "Отправить на заправку",
    ),
    OperationType.REFILL_DONE: TransitionRule(
        {CartridgeStatus.IN_REFILL}, CartridgeStatus.IN_STOCK, "Вернуть с заправки"
    ),
    OperationType.SEND_RESTORE: TransitionRule(
        {CartridgeStatus.IN_STOCK, CartridgeStatus.ISSUED},
        CartridgeStatus.IN_RESTORE,
        "Отправить на восстановление",
    ),
    OperationType.RESTORE_DONE: TransitionRule(
        {CartridgeStatus.IN_RESTORE}, CartridgeStatus.IN_STOCK, "Вернуть с восстановления"
    ),
    OperationType.WRITE_OFF: TransitionRule(
        {
            CartridgeStatus.IN_STOCK,
            CartridgeStatus.ISSUED,
            CartridgeStatus.INSTALLED,
            CartridgeStatus.IN_REFILL,
            CartridgeStatus.IN_RESTORE,
        },
        CartridgeStatus.WRITTEN_OFF,
        "Списать",
    ),
}

STATUS_TITLES = {
    CartridgeStatus.IN_STOCK: "на складе",
    CartridgeStatus.ISSUED: "выдан сотруднику",
    CartridgeStatus.INSTALLED: "установлен в принтер",
    CartridgeStatus.IN_REFILL: "на заправке",
    CartridgeStatus.IN_RESTORE: "на восстановлении",
    CartridgeStatus.WRITTEN_OFF: "списан",
}


def _get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if not employee.is_active:
        raise HTTPException(status_code=409, detail="Сотрудник деактивирован")
    return employee


def _get_service_provider(db: Session, provider_id: int) -> ServiceProvider:
    provider = db.get(ServiceProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Сервисная организация не найдена")
    if not provider.is_active:
        raise HTTPException(
            status_code=409, detail="Сервисная организация деактивирована"
        )
    return provider


def _get_printer(db: Session, printer_id: int) -> Printer:
    printer = db.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Принтер не найден")
    if printer.status == PrinterStatus.RETIRED:
        raise HTTPException(status_code=409, detail="Принтер списан, установка невозможна")
    return printer


def _resolve_attribution(
    db: Session,
    cartridge: Cartridge,
    payload: OperationCreate,
    employee_id: int | None,
    printer_id: int | None,
) -> tuple[int | None, int | None]:
    """Юрлицо и отдел, на которые относится операция."""
    if payload.type in {OperationType.REFILL_DONE, OperationType.RESTORE_DONE}:
        source_type = (
            OperationType.SEND_REFILL
            if payload.type == OperationType.REFILL_DONE
            else OperationType.SEND_RESTORE
        )
        db.flush()
        source = db.scalar(
            select(Operation)
            .where(
                Operation.cartridge_id == cartridge.id,
                Operation.type == source_type,
            )
            .order_by(Operation.id.desc())
            .limit(1)
        )
        if source is not None and source.department_id is not None:
            return source.department_id, source.legal_entity_id

    department = None
    if employee_id is not None:
        employee = db.get(Employee, employee_id)
        if employee is not None:
            department = employee.department
    if department is None and printer_id is not None:
        printer = db.get(Printer, printer_id)
        if printer is not None and printer.employee is not None:
            department = printer.employee.department
    if department is None:
        return cartridge.department_id, cartridge.legal_entity_id
    return department.id, department.legal_entity_id


def perform_operation(
    db: Session,
    cartridge: Cartridge,
    payload: OperationCreate,
    user_id: int | None,
) -> Operation:
    if payload.type == OperationType.RECEIPT:
        raise HTTPException(
            status_code=400,
            detail="Приход оформляется созданием картриджа",
        )

    rule = TRANSITIONS[payload.type]
    if cartridge.status not in rule.allowed_from:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Операция «{rule.title}» недоступна: картридж "
                f"{STATUS_TITLES[cartridge.status]}"
            ),
        )

    holder_employee_id = (
        payload.employee_id if payload.employee_id is not None else cartridge.employee_id
    )
    holder_printer_id = (
        payload.printer_id if payload.printer_id is not None else cartridge.printer_id
    )
    if payload.type == OperationType.INSTALL and payload.printer_id is not None:
        holder_employee_id = None
        holder_printer_id = payload.printer_id

    effective_time = (
        payload.occurred_at.astimezone(timezone.utc)
        if payload.occurred_at is not None
        else datetime.now(timezone.utc)
    )
    service_provider_id = payload.service_provider_id
    service_result = payload.result

    if payload.type == OperationType.ISSUE:
        if payload.employee_id is None:
            raise HTTPException(status_code=422, detail="Укажите сотрудника")
        _get_employee(db, payload.employee_id)
        cartridge.employee_id = payload.employee_id
        cartridge.printer_id = None

    elif payload.type == OperationType.INSTALL:
        if payload.printer_id is None:
            raise HTTPException(status_code=422, detail="Укажите принтер")
        _get_printer(db, payload.printer_id)
        cartridge.printer_id = payload.printer_id
        cartridge.employee_id = None

    elif payload.type == OperationType.UNINSTALL:
        if payload.printer_id is None and cartridge.printer_id is not None:
            payload = payload.model_copy(
                update={"printer_id": cartridge.printer_id}
            )
        cartridge.printer_id = None

    elif payload.type == OperationType.RETURN:
        if payload.employee_id is None:
            payload = payload.model_copy(
                update={"employee_id": cartridge.employee_id}
            )
        cartridge.employee_id = None

    elif payload.type in {OperationType.SEND_REFILL, OperationType.SEND_RESTORE}:
        if (
            payload.type == OperationType.SEND_REFILL
            and not cartridge.model.refillable
        ):
            raise HTTPException(
                status_code=409,
                detail="Эта модель картриджа не подлежит заправке",
            )
        if payload.employee_id is None:
            payload = payload.model_copy(
                update={"employee_id": cartridge.employee_id}
            )
        if payload.printer_id is None:
            payload = payload.model_copy(update={"printer_id": cartridge.printer_id})
        if payload.service_provider_id is None:
            raise HTTPException(
                status_code=422, detail="Укажите сервисную организацию"
            )
        provider = _get_service_provider(db, payload.service_provider_id)
        cartridge.service_provider_id = provider.id
        cartridge.service_since = effective_time
        cartridge.expected_return_date = payload.expected_return_date
        cartridge.employee_id = None
        cartridge.printer_id = None

    elif payload.type == OperationType.WRITE_OFF:
        if payload.employee_id is None and cartridge.employee_id is not None:
            payload = payload.model_copy(
                update={"employee_id": cartridge.employee_id}
            )
        if payload.printer_id is None and cartridge.printer_id is not None:
            payload = payload.model_copy(
                update={"printer_id": cartridge.printer_id}
            )
        cartridge.employee_id = None
        cartridge.printer_id = None

    if payload.type == OperationType.REFILL_DONE:
        cartridge.refill_count += 1

    if payload.type in {OperationType.REFILL_DONE, OperationType.RESTORE_DONE}:
        service_provider_id = (
            payload.service_provider_id
            if payload.service_provider_id is not None
            else cartridge.service_provider_id
        )
        if service_result is None:
            service_result = (
                ServiceResult.REFILLED
                if payload.type == OperationType.REFILL_DONE
                else ServiceResult.RESTORED
            )
        cartridge.service_provider_id = None
        cartridge.service_since = None
        cartridge.expected_return_date = None
    elif payload.type == OperationType.WRITE_OFF and cartridge.status in {
        CartridgeStatus.IN_REFILL,
        CartridgeStatus.IN_RESTORE,
    }:
        service_provider_id = (
            payload.service_provider_id
            if payload.service_provider_id is not None
            else cartridge.service_provider_id
        )
        if service_result is None:
            service_result = ServiceResult.UNREPAIRABLE
        cartridge.service_provider_id = None
        cartridge.service_since = None
        cartridge.expected_return_date = None

    department_id, legal_entity_id = _resolve_attribution(
        db, cartridge, payload, holder_employee_id, holder_printer_id
    )
    if department_id is not None:
        cartridge.department_id = department_id
        cartridge.legal_entity_id = legal_entity_id
    elif payload.type in {OperationType.ISSUE, OperationType.INSTALL}:
        cartridge.department_id = None
        cartridge.legal_entity_id = None

    from_status = cartridge.status
    cartridge.status = rule.to

    operation = Operation(
        cartridge=cartridge,
        type=payload.type,
        from_status=from_status,
        to_status=rule.to,
        employee_id=payload.employee_id,
        printer_id=payload.printer_id,
        legal_entity_id=legal_entity_id,
        department_id=department_id,
        service_provider_id=service_provider_id,
        expected_return_date=(
            payload.expected_return_date
            if payload.type
            in {OperationType.SEND_REFILL, OperationType.SEND_RESTORE}
            else None
        ),
        result=service_result,
        cost=payload.cost,
        document_no=payload.document_no,
        comment=payload.comment,
        user_id=user_id,
    )
    if payload.occurred_at is not None:
        operation.occurred_at = payload.occurred_at.astimezone(timezone.utc)
    db.add(operation)
    return operation


def create_cartridge(
    db: Session,
    *,
    inventory_no: str,
    serial_no: str | None,
    model_id: int,
    purchase_price,
    purchase_date,
    notes: str | None,
    comment: str | None,
    user_id: int | None,
    received_at: datetime | None = None,
) -> Cartridge:
    cartridge = Cartridge(
        inventory_no=inventory_no,
        serial_no=serial_no,
        model_id=model_id,
        status=CartridgeStatus.IN_STOCK,
        purchase_price=purchase_price,
        purchase_date=purchase_date,
        notes=notes,
    )
    db.add(cartridge)
    db.flush()

    operation = Operation(
        cartridge_id=cartridge.id,
        type=OperationType.RECEIPT,
        from_status=None,
        to_status=CartridgeStatus.IN_STOCK,
        cost=purchase_price,
        comment=comment,
        user_id=user_id,
    )
    if received_at is not None:
        operation.occurred_at = received_at
    db.add(operation)
    return cartridge
