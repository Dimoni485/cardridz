from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutil import local_day_start
from app.models import Cartridge, Operation, Printer, PrinterRepair
from app.models.enums import OperationType

MONEY_FORMAT = '#,##0.00" ₽"'
DATE_FORMAT = "DD.MM.YYYY"

HEADER_FILL = PatternFill("solid", fgColor="1E3A8A")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
SUBTITLE_FONT = Font(italic=True, color="475569")
TOTAL_FONT = Font(bold=True)
THIN = Side(style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

DETAIL_HEADERS = [
    "Дата",
    "Юрлицо",
    "Отдел",
    "Тип объекта",
    "Модель",
    "Инвентарный номер",
    "Вид обслуживания",
    "Сервисная организация",
    "Документ",
    "Стоимость, ₽",
]

DETAIL_WIDTHS = [12, 30, 24, 14, 32, 18, 18, 30, 16, 16]


def _local_date(moment) -> date:
    return moment.astimezone().date()


def _collect_rows(db: Session, start, end) -> list[dict]:
    rows: list[dict] = []

    cartridge_operations = db.scalars(
        select(Operation)
        .options(
            selectinload(Operation.cartridge).selectinload(Cartridge.model),
            selectinload(Operation.legal_entity),
            selectinload(Operation.department),
            selectinload(Operation.service_provider),
        )
        .where(
            Operation.type.in_(
                [OperationType.REFILL_DONE, OperationType.RESTORE_DONE]
            ),
            Operation.occurred_at >= start,
            Operation.occurred_at < end,
        )
    ).all()

    for operation in cartridge_operations:
        cartridge = operation.cartridge
        rows.append(
            {
                "date": _local_date(operation.occurred_at),
                "legal_entity": (
                    operation.legal_entity.name
                    if operation.legal_entity
                    else "Без юрлица"
                ),
                "department": (
                    operation.department.name if operation.department else "—"
                ),
                "object_type": "Картридж",
                "model": f"{cartridge.model.vendor} {cartridge.model.name}",
                "inventory_no": cartridge.inventory_no,
                "service_type": (
                    "Заправка"
                    if operation.type == OperationType.REFILL_DONE
                    else "Восстановление"
                ),
                "provider": (
                    operation.service_provider.name
                    if operation.service_provider
                    else "—"
                ),
                "document": operation.document_no or "—",
                "cost": float(operation.cost or 0),
                "sort_key": (
                    operation.legal_entity.name if operation.legal_entity else "~",
                    operation.department.name if operation.department else "~",
                    _local_date(operation.occurred_at),
                ),
            }
        )

    repairs = db.scalars(
        select(PrinterRepair)
        .options(
            selectinload(PrinterRepair.printer).selectinload(Printer.model),
            selectinload(PrinterRepair.legal_entity),
            selectinload(PrinterRepair.department),
            selectinload(PrinterRepair.service_provider),
        )
        .where(
            PrinterRepair.status == "returned",
            PrinterRepair.returned_at >= start,
            PrinterRepair.returned_at < end,
        )
    ).all()

    for repair in repairs:
        rows.append(
            {
                "date": _local_date(repair.returned_at),
                "legal_entity": (
                    repair.legal_entity.name
                    if repair.legal_entity
                    else "Без юрлица"
                ),
                "department": (
                    repair.department.name if repair.department else "—"
                ),
                "object_type": "Принтер",
                "model": f"{repair.printer.model.vendor} {repair.printer.model.name}",
                "inventory_no": repair.printer.inventory_no,
                "service_type": "Ремонт",
                "provider": (
                    repair.service_provider.name
                    if repair.service_provider
                    else "—"
                ),
                "document": repair.document_no or "—",
                "cost": float(repair.cost or 0),
                "sort_key": (
                    repair.legal_entity.name if repair.legal_entity else "~",
                    repair.department.name if repair.department else "~",
                    _local_date(repair.returned_at),
                ),
            }
        )

    rows.sort(key=lambda row: row["sort_key"])
    return rows


def _write_header(ws, row: int, headers: list[str], widths: list[int]) -> None:
    for index, (title, width) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=row, column=index, value=title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.row_dimensions[row].height = 32


def _write_title(
    ws, title: str, date_from: date, date_to: date, last_column: int
) -> None:
    ws.merge_cells(
        start_row=1, start_column=1, end_row=1, end_column=last_column
    )
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = TITLE_FONT
    cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells(
        start_row=2, start_column=1, end_row=2, end_column=last_column
    )
    period = ws.cell(
        row=2,
        column=1,
        value=(
            "Период: "
            f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"
        ),
    )
    period.font = SUBTITLE_FONT


def build_service_export(
    db: Session, date_from: date, date_to: date
) -> BytesIO:
    start = local_day_start(date_from)
    end = local_day_start(date_to + timedelta(days=1))
    rows = _collect_rows(db, start, end)

    workbook = Workbook()
    workbook.properties.title = "Cardridz — отчёт по обслуживанию"
    workbook.properties.creator = "Cardridz"

    detail = workbook.active
    detail.title = "Обслуживание"
    _write_title(
        detail,
        "Отчёт по обслуживанию картриджей и принтеров",
        date_from,
        date_to,
        len(DETAIL_HEADERS),
    )
    _write_header(detail, 4, DETAIL_HEADERS, DETAIL_WIDTHS)

    data_start = 5
    for offset, row in enumerate(rows):
        excel_row = data_start + offset
        values = [
            row["date"],
            row["legal_entity"],
            row["department"],
            row["object_type"],
            row["model"],
            row["inventory_no"],
            row["service_type"],
            row["provider"],
            row["document"],
            row["cost"],
        ]
        for column, value in enumerate(values, start=1):
            cell = detail.cell(row=excel_row, column=column, value=value)
            cell.border = BORDER
            if column == 1:
                cell.number_format = DATE_FORMAT
                cell.alignment = CENTER
            elif column == 10:
                cell.number_format = MONEY_FORMAT

    if rows:
        last_data_row = data_start + len(rows) - 1
        total_row = last_data_row + 1
        detail.merge_cells(
            start_row=total_row,
            start_column=1,
            end_row=total_row,
            end_column=9,
        )
        label = detail.cell(row=total_row, column=1, value="Итого за период")
        label.font = TOTAL_FONT
        label.alignment = Alignment(horizontal="right")
        total_cell = detail.cell(
            row=total_row, column=10, value=sum(row["cost"] for row in rows)
        )
        total_cell.font = TOTAL_FONT
        total_cell.number_format = MONEY_FORMAT
        for column in range(1, 11):
            detail.cell(row=total_row, column=column).border = BORDER
        detail.auto_filter.ref = f"A4:J{last_data_row}"
    else:
        detail.merge_cells(
            start_row=5, start_column=1, end_row=5, end_column=10
        )
        detail.cell(
            row=5,
            column=1,
            value="За выбранный период операций обслуживания нет",
        ).alignment = Alignment(horizontal="center")
    detail.freeze_panes = "A5"

    summary = workbook.create_sheet("Итого по юрлицам")
    summary_headers = ["Юрлицо", "Заправка", "Восстановление", "Ремонт", "Итого"]
    summary_widths = [34, 16, 18, 14, 16]
    _write_title(
        summary, "Итоги по юрлицам", date_from, date_to, len(summary_headers)
    )
    _write_header(summary, 4, summary_headers, summary_widths)

    totals_by_entity: dict[str, dict[str, float]] = defaultdict(
        lambda: {"refill": 0.0, "restore": 0.0, "repair": 0.0}
    )
    for row in rows:
        bucket = totals_by_entity[row["legal_entity"]]
        if row["service_type"] == "Заправка":
            bucket["refill"] += row["cost"]
        elif row["service_type"] == "Восстановление":
            bucket["restore"] += row["cost"]
        else:
            bucket["repair"] += row["cost"]

    summary_row = 5
    for entity_name in sorted(totals_by_entity):
        values = totals_by_entity[entity_name]
        total = values["refill"] + values["restore"] + values["repair"]
        for column, value in enumerate(
            [
                entity_name,
                values["refill"],
                values["restore"],
                values["repair"],
                total,
            ],
            start=1,
        ):
            cell = summary.cell(row=summary_row, column=column, value=value)
            cell.border = BORDER
            if column > 1:
                cell.number_format = MONEY_FORMAT
        summary_row += 1

    if totals_by_entity:
        summary.merge_cells(
            start_row=summary_row,
            start_column=1,
            end_row=summary_row,
            end_column=4,
        )
        label = summary.cell(row=summary_row, column=1, value="Итого")
        label.font = TOTAL_FONT
        label.alignment = Alignment(horizontal="right")
        grand_total = sum(
            values["refill"] + values["restore"] + values["repair"]
            for values in totals_by_entity.values()
        )
        total_cell = summary.cell(row=summary_row, column=5, value=grand_total)
        total_cell.font = TOTAL_FONT
        total_cell.number_format = MONEY_FORMAT
        for column in range(1, 6):
            summary.cell(row=summary_row, column=column).border = BORDER
    summary.freeze_panes = "A5"

    departments = workbook.create_sheet("Итого по отделам")
    department_headers = [
        "Юрлицо",
        "Отдел",
        "Заправка",
        "Восстановление",
        "Ремонт",
        "Итого",
    ]
    department_widths = [32, 26, 16, 18, 14, 16]
    _write_title(
        departments,
        "Итоги по отделам",
        date_from,
        date_to,
        len(department_headers),
    )
    _write_header(departments, 4, department_headers, department_widths)

    department_totals: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"refill": 0.0, "restore": 0.0, "repair": 0.0}
    )
    for row in rows:
        bucket = department_totals[(row["legal_entity"], row["department"])]
        if row["service_type"] == "Заправка":
            bucket["refill"] += row["cost"]
        elif row["service_type"] == "Восстановление":
            bucket["restore"] += row["cost"]
        else:
            bucket["repair"] += row["cost"]

    department_row = 5
    for (entity_name, department_name) in sorted(department_totals):
        values = department_totals[(entity_name, department_name)]
        total = values["refill"] + values["restore"] + values["repair"]
        for column, value in enumerate(
            [
                entity_name,
                department_name,
                values["refill"],
                values["restore"],
                values["repair"],
                total,
            ],
            start=1,
        ):
            cell = departments.cell(row=department_row, column=column, value=value)
            cell.border = BORDER
            if column > 2:
                cell.number_format = MONEY_FORMAT
        department_row += 1

    if department_totals:
        departments.merge_cells(
            start_row=department_row,
            start_column=1,
            end_row=department_row,
            end_column=2,
        )
        label = departments.cell(row=department_row, column=1, value="Итого")
        label.font = TOTAL_FONT
        label.alignment = Alignment(horizontal="right")
        for column, key in enumerate(
            ["refill", "restore", "repair"], start=3
        ):
            value = sum(bucket[key] for bucket in department_totals.values())
            cell = departments.cell(row=department_row, column=column, value=value)
            cell.font = TOTAL_FONT
            cell.number_format = MONEY_FORMAT
        grand_total = sum(
            bucket["refill"] + bucket["restore"] + bucket["repair"]
            for bucket in department_totals.values()
        )
        total_cell = departments.cell(
            row=department_row, column=6, value=grand_total
        )
        total_cell.font = TOTAL_FONT
        total_cell.number_format = MONEY_FORMAT
        for column in range(1, 7):
            departments.cell(row=department_row, column=column).border = BORDER
    departments.freeze_panes = "A5"

    providers = workbook.create_sheet("Итого по сервисным организациям")
    provider_headers = [
        "Сервисная организация",
        "Заправка",
        "Восстановление",
        "Ремонт",
        "Итого",
    ]
    provider_widths = [34, 16, 18, 14, 16]
    _write_title(
        providers,
        "Итоги по сервисным организациям",
        date_from,
        date_to,
        len(provider_headers),
    )
    _write_header(providers, 4, provider_headers, provider_widths)

    provider_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"refill": 0.0, "restore": 0.0, "repair": 0.0}
    )
    for row in rows:
        bucket = provider_totals[row["provider"]]
        if row["service_type"] == "Заправка":
            bucket["refill"] += row["cost"]
        elif row["service_type"] == "Восстановление":
            bucket["restore"] += row["cost"]
        else:
            bucket["repair"] += row["cost"]

    provider_row = 5
    for provider_name in sorted(provider_totals):
        values = provider_totals[provider_name]
        total = values["refill"] + values["restore"] + values["repair"]
        for column, value in enumerate(
            [
                provider_name,
                values["refill"],
                values["restore"],
                values["repair"],
                total,
            ],
            start=1,
        ):
            cell = providers.cell(row=provider_row, column=column, value=value)
            cell.border = BORDER
            if column > 1:
                cell.number_format = MONEY_FORMAT
        provider_row += 1

    if provider_totals:
        providers.merge_cells(
            start_row=provider_row,
            start_column=1,
            end_row=provider_row,
            end_column=4,
        )
        label = providers.cell(row=provider_row, column=1, value="Итого")
        label.font = TOTAL_FONT
        label.alignment = Alignment(horizontal="right")
        grand_total = sum(
            values["refill"] + values["restore"] + values["repair"]
            for values in provider_totals.values()
        )
        total_cell = providers.cell(row=provider_row, column=5, value=grand_total)
        total_cell.font = TOTAL_FONT
        total_cell.number_format = MONEY_FORMAT
        for column in range(1, 6):
            providers.cell(row=provider_row, column=column).border = BORDER
    providers.freeze_panes = "A5"

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
