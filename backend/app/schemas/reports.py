from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    CartridgeColor,
    CartridgeKind,
    CartridgeStatus,
    OperationType,
)
from app.schemas.cartridge import OperationRead


class LowStockItem(BaseModel):
    model_id: int
    vendor: str
    name: str
    color: CartridgeColor
    in_stock: int
    min_stock: int
    shortage: int


class SummaryStats(BaseModel):
    total_cartridges: int
    total_models: int
    total_printers: int
    total_employees: int
    by_status: dict[str, int]
    low_stock: list[LowStockItem]
    recent_operations: list[OperationRead]


class StockRow(BaseModel):
    model_id: int
    vendor: str
    name: str
    color: CartridgeColor
    kind: CartridgeKind
    resource_pages: int | None = None
    min_stock: int
    in_stock: int
    issued: int
    installed: int
    in_refill: int
    in_restore: int
    written_off: int
    total: int
    refills: int


class StockReport(BaseModel):
    rows: list[StockRow]
    totals: dict[str, int]


class OperationTypeStat(BaseModel):
    type: OperationType
    count: int
    cost: float


class OperationDayStat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    count: int


class OperationsReport(BaseModel):
    date_from: date
    date_to: date
    total_operations: int
    total_cost: float
    by_type: list[OperationTypeStat]
    by_day: list[OperationDayStat]


class EmployeeRow(BaseModel):
    employee_id: int
    full_name: str
    department: str | None = None
    legal_entity: str | None = None
    is_active: bool
    issued: int
    installed_at_printers: int
    total: int


class EmployeesReport(BaseModel):
    rows: list[EmployeeRow]


class UsageRow(BaseModel):
    legal_entity_id: int | None = None
    legal_entity_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    issued_count: int
    cartridges_cost: float
    service_cost: float
    repair_cost: float
    total_cost: float


class UsageEntityRow(BaseModel):
    legal_entity_id: int | None = None
    legal_entity_name: str | None = None
    issued_count: int
    cartridges_cost: float
    service_cost: float
    repair_cost: float
    total_cost: float


class UsageTotals(BaseModel):
    issued_count: int
    cartridges_cost: float
    service_cost: float
    repair_cost: float
    total_cost: float


class UsageReport(BaseModel):
    year: int
    month: int
    date_from: date
    date_to: date
    rows: list[UsageRow]
    by_legal_entity: list[UsageEntityRow]
    totals: UsageTotals


class ServiceProviderStat(BaseModel):
    provider_id: int | None = None
    provider_name: str | None = None
    sent_count: int
    returned_count: int
    cost: float
    outstanding_count: int
    printer_cost: float
    printer_sent_count: int
    printer_returned_count: int
    printer_outstanding_count: int


class ServiceOutstandingRow(BaseModel):
    cartridge_id: int
    inventory_no: str
    model_name: str
    status: CartridgeStatus
    provider_id: int | None = None
    provider_name: str | None = None
    service_since: date | None = None
    expected_return_date: date | None = None
    overdue: bool


class ServiceTotals(BaseModel):
    sent_count: int
    returned_count: int
    cost: float
    outstanding_count: int
    printer_cost: float
    printer_sent_count: int
    printer_returned_count: int
    printer_cost: float
    printer_outstanding_count: int


class PrinterOutstandingRow(BaseModel):
    printer_id: int
    inventory_no: str
    model_name: str
    provider_id: int | None = None
    provider_name: str | None = None
    service_since: date | None = None
    expected_return_date: date | None = None
    overdue: bool


class ServiceReport(BaseModel):
    year: int
    month: int
    date_from: date
    date_to: date
    rows: list[ServiceProviderStat]
    totals: ServiceTotals
    outstanding: list[ServiceOutstandingRow]
    printers_outstanding: list[PrinterOutstandingRow]
