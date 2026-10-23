from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutil import local_day_start, local_month_range
from app.models import (
    Cartridge,
    CartridgeModel,
    Department,
    Employee,
    LegalEntity,
    Operation,
    Printer,
    PrinterRepair,
    ServiceProvider,
)
from app.models.enums import CartridgeStatus, OperationType
from app.schemas.reports import (
    EmployeeRow,
    EmployeesReport,
    LowStockItem,
    OperationDayStat,
    OperationsReport,
    OperationTypeStat,
    StockReport,
    StockRow,
    PrinterOutstandingRow,
    ServiceOutstandingRow,
    ServiceProviderStat,
    ServiceReport,
    ServiceTotals,
    SummaryStats,
    UsageEntityRow,
    UsageReport,
    UsageRow,
    UsageTotals,
)
from app.services.loaders import OPERATION_LOADS

def _status_counts(db: Session) -> dict[str, int]:
    counts = {status.value: 0 for status in CartridgeStatus}
    rows = db.execute(
        select(Cartridge.status, func.count(Cartridge.id)).group_by(Cartridge.status)
    ).all()
    for status_value, count in rows:
        counts[status_value.value] = count
    return counts


def get_summary(db: Session) -> SummaryStats:
    by_status = _status_counts(db)

    models = db.scalars(select(CartridgeModel)).all()
    stock_rows = db.execute(
        select(Cartridge.model_id, func.count(Cartridge.id))
        .where(Cartridge.status == CartridgeStatus.IN_STOCK)
        .group_by(Cartridge.model_id)
    ).all()
    in_stock = dict(stock_rows)

    low_stock = [
        LowStockItem(
            model_id=model.id,
            vendor=model.vendor,
            name=model.name,
            color=model.color,
            in_stock=in_stock.get(model.id, 0),
            min_stock=model.min_stock,
            shortage=max(model.min_stock - in_stock.get(model.id, 0), 0),
        )
        for model in models
        if model.min_stock > 0 and in_stock.get(model.id, 0) < model.min_stock
    ]

    recent_operations = db.scalars(
        select(Operation)
        .options(*OPERATION_LOADS)
        .order_by(Operation.occurred_at.desc(), Operation.id.desc())
        .limit(10)
    ).all()

    return SummaryStats(
        total_cartridges=sum(by_status.values()),
        total_models=len(models),
        total_printers=db.scalar(select(func.count(Printer.id))) or 0,
        total_employees=db.scalar(select(func.count(Employee.id))) or 0,
        by_status=by_status,
        low_stock=low_stock,
        recent_operations=list(recent_operations),
    )


def get_stock_report(db: Session) -> StockReport:
    models = db.scalars(
        select(CartridgeModel).order_by(CartridgeModel.vendor, CartridgeModel.name)
    ).all()

    counts: dict[int, dict[str, int]] = {}
    for model_id, status, count in db.execute(
        select(Cartridge.model_id, Cartridge.status, func.count(Cartridge.id)).group_by(
            Cartridge.model_id, Cartridge.status
        )
    ).all():
        counts.setdefault(model_id, {})[status.value] = count

    refills = dict(
        db.execute(
            select(
                Cartridge.model_id, func.coalesce(func.sum(Cartridge.refill_count), 0)
            ).group_by(Cartridge.model_id)
        ).all()
    )

    rows: list[StockRow] = []
    for model in models:
        model_counts = counts.get(model.id, {})
        total = sum(model_counts.values())
        rows.append(
            StockRow(
                model_id=model.id,
                vendor=model.vendor,
                name=model.name,
                color=model.color,
                kind=model.kind,
                resource_pages=model.resource_pages,
                min_stock=model.min_stock,
                in_stock=model_counts.get(CartridgeStatus.IN_STOCK.value, 0),
                issued=model_counts.get(CartridgeStatus.ISSUED.value, 0),
                installed=model_counts.get(CartridgeStatus.INSTALLED.value, 0),
                in_refill=model_counts.get(CartridgeStatus.IN_REFILL.value, 0),
                in_restore=model_counts.get(CartridgeStatus.IN_RESTORE.value, 0),
                written_off=model_counts.get(CartridgeStatus.WRITTEN_OFF.value, 0),
                total=total,
                refills=int(refills.get(model.id, 0)),
            )
        )

    totals = {
        "models": len(models),
        "total": sum(row.total for row in rows),
        "in_stock": sum(row.in_stock for row in rows),
        "issued": sum(row.issued for row in rows),
        "installed": sum(row.installed for row in rows),
        "in_refill": sum(row.in_refill for row in rows),
        "in_restore": sum(row.in_restore for row in rows),
        "written_off": sum(row.written_off for row in rows),
        "refills": sum(row.refills for row in rows),
    }
    return StockReport(rows=rows, totals=totals)


def get_operations_report(
    db: Session, date_from: date, date_to: date
) -> OperationsReport:
    start = local_day_start(date_from)
    end = local_day_start(date_to + timedelta(days=1))

    rows = db.execute(
        select(
            Operation.type,
            func.count(Operation.id),
            func.coalesce(func.sum(Operation.cost), 0),
        )
        .where(Operation.occurred_at >= start, Operation.occurred_at < end)
        .group_by(Operation.type)
    ).all()
    by_type = [
        OperationTypeStat(type=op_type, count=count, cost=float(cost))
        for op_type, count, cost in rows
    ]
    by_type.sort(key=lambda item: item.count, reverse=True)

    day_rows = db.execute(
        select(
            func.date(Operation.occurred_at).label("day"),
            func.count(Operation.id),
        )
        .where(Operation.occurred_at >= start, Operation.occurred_at < end)
        .group_by("day")
        .order_by("day")
    ).all()

    total_operations = sum(item.count for item in by_type)
    total_cost = sum(
        item.cost for item in by_type if item.type != OperationType.RECEIPT
    )

    return OperationsReport(
        date_from=date_from,
        date_to=date_to,
        total_operations=total_operations,
        total_cost=total_cost,
        by_type=by_type,
        by_day=[OperationDayStat(day=day, count=count) for day, count in day_rows],
    )


def get_employees_report(db: Session) -> EmployeesReport:
    employees = db.scalars(
        select(Employee)
        .options(
            selectinload(Employee.department).selectinload(Department.legal_entity)
        )
        .order_by(Employee.is_active.desc(), Employee.full_name)
    ).all()

    issued = dict(
        db.execute(
            select(Cartridge.employee_id, func.count(Cartridge.id))
            .where(
                Cartridge.status == CartridgeStatus.ISSUED,
                Cartridge.employee_id.is_not(None),
            )
            .group_by(Cartridge.employee_id)
        ).all()
    )

    installed = dict(
        db.execute(
            select(Printer.employee_id, func.count(Cartridge.id))
            .join(Cartridge, Cartridge.printer_id == Printer.id)
            .where(
                Cartridge.status == CartridgeStatus.INSTALLED,
                Printer.employee_id.is_not(None),
            )
            .group_by(Printer.employee_id)
        ).all()
    )

    rows = [
        EmployeeRow(
            employee_id=employee.id,
            full_name=employee.full_name,
            department=employee.department.name if employee.department else None,
            legal_entity=(
                employee.department.legal_entity.name
                if employee.department
                else None
            ),
            is_active=employee.is_active,
            issued=issued.get(employee.id, 0),
            installed_at_printers=installed.get(employee.id, 0),
            total=issued.get(employee.id, 0) + installed.get(employee.id, 0),
        )
        for employee in employees
    ]
    return EmployeesReport(rows=rows)



def get_usage_report(db: Session, year: int, month: int) -> UsageReport:
    start, end = local_month_range(year, month)

    issue_rows = db.execute(
        select(
            Operation.legal_entity_id,
            Operation.department_id,
            func.count(Operation.id),
            func.coalesce(
                func.sum(
                    func.coalesce(Operation.cost, Cartridge.purchase_price, 0)
                ),
                0,
            ),
        )
        .join(Cartridge, Operation.cartridge_id == Cartridge.id)
        .where(
            Operation.type == OperationType.ISSUE,
            Operation.occurred_at >= start,
            Operation.occurred_at < end,
        )
        .group_by(Operation.legal_entity_id, Operation.department_id)
    ).all()

    service_rows = db.execute(
        select(
            Operation.legal_entity_id,
            Operation.department_id,
            func.coalesce(func.sum(Operation.cost), 0),
        )
        .where(
            Operation.type.in_(
                [OperationType.REFILL_DONE, OperationType.RESTORE_DONE]
            ),
            Operation.occurred_at >= start,
            Operation.occurred_at < end,
        )
        .group_by(Operation.legal_entity_id, Operation.department_id)
    ).all()

    repair_rows = db.execute(
        select(
            PrinterRepair.legal_entity_id,
            PrinterRepair.department_id,
            func.coalesce(func.sum(PrinterRepair.cost), 0),
        )
        .where(
            PrinterRepair.status == "returned",
            PrinterRepair.returned_at >= start,
            PrinterRepair.returned_at < end,
        )
        .group_by(PrinterRepair.legal_entity_id, PrinterRepair.department_id)
    ).all()

    entity_names = dict(
        db.execute(select(LegalEntity.id, LegalEntity.name)).all()
    )
    dept_rows = db.execute(
        select(Department.id, Department.name, Department.legal_entity_id)
    ).all()
    department_names = {dept_id: name for dept_id, name, _ in dept_rows}
    department_entities = {
        dept_id: entity_id for dept_id, _, entity_id in dept_rows
    }

    aggregated: dict[tuple[int | None, int | None], dict[str, float | int]] = {}

    def bucket(entity_id: int | None, department_id: int | None) -> dict:
        key = (entity_id, department_id)
        return aggregated.setdefault(
            key,
            {
                "issued_count": 0,
                "cartridges_cost": 0.0,
                "service_cost": 0.0,
                "repair_cost": 0.0,
            },
        )

    for entity_id, department_id, count, cost in issue_rows:
        if entity_id is None and department_id is not None:
            entity_id = department_entities.get(department_id)
        item = bucket(entity_id, department_id)
        item["issued_count"] += int(count)
        item["cartridges_cost"] += float(cost or 0)

    for entity_id, department_id, cost in service_rows:
        if entity_id is None and department_id is not None:
            entity_id = department_entities.get(department_id)
        item = bucket(entity_id, department_id)
        item["service_cost"] += float(cost or 0)

    for entity_id, department_id, cost in repair_rows:
        if entity_id is None and department_id is not None:
            entity_id = department_entities.get(department_id)
        item = bucket(entity_id, department_id)
        item["repair_cost"] += float(cost or 0)

    rows: list[UsageRow] = []
    for (entity_id, department_id), values in aggregated.items():
        cartridges_cost = float(values["cartridges_cost"])
        service_cost = float(values["service_cost"])
        repair_cost = float(values["repair_cost"])
        rows.append(
            UsageRow(
                legal_entity_id=entity_id,
                legal_entity_name=entity_names.get(entity_id),
                department_id=department_id,
                department_name=department_names.get(department_id),
                issued_count=int(values["issued_count"]),
                cartridges_cost=cartridges_cost,
                service_cost=service_cost,
                repair_cost=repair_cost,
                total_cost=cartridges_cost + service_cost + repair_cost,
            )
        )

    rows.sort(
        key=lambda row: (
            row.legal_entity_name is None,
            row.legal_entity_name or "",
            row.department_name is None,
            row.department_name or "",
        )
    )

    entity_totals: dict[int | None, UsageEntityRow] = {}
    for row in rows:
        entity = entity_totals.get(row.legal_entity_id)
        if entity is None:
            entity = UsageEntityRow(
                legal_entity_id=row.legal_entity_id,
                legal_entity_name=row.legal_entity_name,
                issued_count=0,
                cartridges_cost=0.0,
                service_cost=0.0,
                repair_cost=0.0,
                total_cost=0.0,
            )
            entity_totals[row.legal_entity_id] = entity
        entity.issued_count += row.issued_count
        entity.cartridges_cost += row.cartridges_cost
        entity.service_cost += row.service_cost
        entity.repair_cost += row.repair_cost
        entity.total_cost += row.total_cost

    by_entity = list(entity_totals.values())
    by_entity.sort(
        key=lambda row: (row.legal_entity_name is None, row.legal_entity_name or "")
    )

    totals = UsageTotals(
        issued_count=sum(row.issued_count for row in rows),
        cartridges_cost=sum(row.cartridges_cost for row in rows),
        service_cost=sum(row.service_cost for row in rows),
        repair_cost=sum(row.repair_cost for row in rows),
        total_cost=sum(row.total_cost for row in rows),
    )

    return UsageReport(
        year=year,
        month=month,
        date_from=start.date(),
        date_to=(end - timedelta(days=1)).date(),
        rows=rows,
        by_legal_entity=by_entity,
        totals=totals,
    )


def get_service_report(db: Session, year: int, month: int) -> ServiceReport:
    start, end = local_month_range(year, month)

    sent_rows = db.execute(
        select(Operation.service_provider_id, func.count(Operation.id))
        .where(
            Operation.type.in_(
                [OperationType.SEND_REFILL, OperationType.SEND_RESTORE]
            ),
            Operation.occurred_at >= start,
            Operation.occurred_at < end,
        )
        .group_by(Operation.service_provider_id)
    ).all()

    returned_rows = db.execute(
        select(
            Operation.service_provider_id,
            func.count(Operation.id),
            func.coalesce(func.sum(Operation.cost), 0),
        )
        .where(
            Operation.type.in_(
                [OperationType.REFILL_DONE, OperationType.RESTORE_DONE]
            ),
            Operation.occurred_at >= start,
            Operation.occurred_at < end,
        )
        .group_by(Operation.service_provider_id)
    ).all()

    printer_sent_rows = db.execute(
        select(PrinterRepair.service_provider_id, func.count(PrinterRepair.id))
        .where(
            PrinterRepair.sent_at >= start,
            PrinterRepair.sent_at < end,
        )
        .group_by(PrinterRepair.service_provider_id)
    ).all()

    printer_returned_rows = db.execute(
        select(
            PrinterRepair.service_provider_id,
            func.count(PrinterRepair.id),
            func.coalesce(func.sum(PrinterRepair.cost), 0),
        )
        .where(
            PrinterRepair.status == "returned",
            PrinterRepair.returned_at >= start,
            PrinterRepair.returned_at < end,
        )
        .group_by(PrinterRepair.service_provider_id)
    ).all()

    provider_names = dict(
        db.execute(select(ServiceProvider.id, ServiceProvider.name)).all()
    )

    outstanding_cartridges = db.scalars(
        select(Cartridge)
        .options(
            selectinload(Cartridge.model),
            selectinload(Cartridge.service_provider),
        )
        .where(
            Cartridge.status.in_(
                [CartridgeStatus.IN_REFILL, CartridgeStatus.IN_RESTORE]
            )
        )
        .order_by(Cartridge.service_since)
    ).all()

    open_repairs = db.scalars(
        select(PrinterRepair)
        .options(
            selectinload(PrinterRepair.service_provider),
            selectinload(PrinterRepair.printer).selectinload(Printer.model),
        )
        .where(PrinterRepair.status == "in_service")
        .order_by(PrinterRepair.sent_at)
    ).all()

    today = date.today()
    outstanding_rows: list[ServiceOutstandingRow] = []
    outstanding_by_provider: dict[int | None, int] = {}
    for cartridge in outstanding_cartridges:
        provider_id = cartridge.service_provider_id
        outstanding_by_provider[provider_id] = (
            outstanding_by_provider.get(provider_id, 0) + 1
        )
        outstanding_rows.append(
            ServiceOutstandingRow(
                cartridge_id=cartridge.id,
                inventory_no=cartridge.inventory_no,
                model_name=f"{cartridge.model.vendor} {cartridge.model.name}",
                status=cartridge.status,
                provider_id=provider_id,
                provider_name=(
                    cartridge.service_provider.name
                    if cartridge.service_provider
                    else None
                ),
                service_since=(
                    cartridge.service_since.date()
                    if cartridge.service_since
                    else None
                ),
                expected_return_date=cartridge.expected_return_date,
                overdue=bool(
                    cartridge.expected_return_date
                    and cartridge.expected_return_date < today
                ),
            )
        )

    printer_outstanding_rows: list[PrinterOutstandingRow] = []
    printers_outstanding_by_provider: dict[int | None, int] = {}
    for repair in open_repairs:
        provider_id = repair.service_provider_id
        printers_outstanding_by_provider[provider_id] = (
            printers_outstanding_by_provider.get(provider_id, 0) + 1
        )
        printer_outstanding_rows.append(
            PrinterOutstandingRow(
                printer_id=repair.printer_id,
                inventory_no=repair.printer.inventory_no,
                model_name=(
                    f"{repair.printer.model.vendor} {repair.printer.model.name}"
                ),
                provider_id=provider_id,
                provider_name=(
                    repair.service_provider.name
                    if repair.service_provider
                    else None
                ),
                service_since=repair.sent_at.date(),
                expected_return_date=repair.expected_return_date,
                overdue=bool(
                    repair.expected_return_date
                    and repair.expected_return_date < today
                ),
            )
        )

    def empty_bucket() -> dict[str, float | int]:
        return {
            "sent_count": 0,
            "returned_count": 0,
            "cost": 0.0,
            "outstanding_count": 0,
            "printer_sent_count": 0,
            "printer_returned_count": 0,
            "printer_cost": 0.0,
            "printer_outstanding_count": 0,
        }

    aggregated: dict[int | None, dict[str, float | int]] = {}
    for provider_id, count in sent_rows:
        aggregated.setdefault(provider_id, empty_bucket())["sent_count"] += int(count)
    for provider_id, count, cost in returned_rows:
        item = aggregated.setdefault(provider_id, empty_bucket())
        item["returned_count"] += int(count)
        item["cost"] += float(cost or 0)
    for provider_id, count in outstanding_by_provider.items():
        aggregated.setdefault(provider_id, empty_bucket())["outstanding_count"] = count
    for provider_id, count in printer_sent_rows:
        aggregated.setdefault(provider_id, empty_bucket())["printer_sent_count"] += int(
            count
        )
    for provider_id, count, cost in printer_returned_rows:
        item = aggregated.setdefault(provider_id, empty_bucket())
        item["printer_returned_count"] += int(count)
        item["printer_cost"] += float(cost or 0)
    for provider_id, count in printers_outstanding_by_provider.items():
        aggregated.setdefault(provider_id, empty_bucket())[
            "printer_outstanding_count"
        ] = count

    rows = [
        ServiceProviderStat(
            provider_id=provider_id,
            provider_name=provider_names.get(provider_id),
            sent_count=int(values["sent_count"]),
            returned_count=int(values["returned_count"]),
            cost=float(values["cost"]),
            outstanding_count=int(values["outstanding_count"]),
            printer_cost=float(values["printer_cost"]),
            printer_sent_count=int(values["printer_sent_count"]),
            printer_returned_count=int(values["printer_returned_count"]),
            printer_outstanding_count=int(values["printer_outstanding_count"]),
        )
        for provider_id, values in aggregated.items()
    ]
    rows.sort(
        key=lambda row: (
            row.provider_name is None,
            row.provider_name or "",
        )
    )

    totals = ServiceTotals(
        sent_count=sum(row.sent_count for row in rows),
        returned_count=sum(row.returned_count for row in rows),
        cost=sum(row.cost for row in rows),
        outstanding_count=sum(row.outstanding_count for row in rows),
        printer_sent_count=sum(row.printer_sent_count for row in rows),
        printer_returned_count=sum(row.printer_returned_count for row in rows),
        printer_cost=sum(row.printer_cost for row in rows),
        printer_outstanding_count=sum(
            row.printer_outstanding_count for row in rows
        ),
    )

    return ServiceReport(
        year=year,
        month=month,
        date_from=start.date(),
        date_to=(end - timedelta(days=1)).date(),
        rows=rows,
        totals=totals,
        outstanding=outstanding_rows,
        printers_outstanding=printer_outstanding_rows,
    )
