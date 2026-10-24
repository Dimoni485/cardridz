from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InvoiceLineKind, InvoiceStatus
from app.schemas.cartridge import CartridgeBrief
from app.schemas.catalog import CartridgeModelBrief
from app.schemas.common import Money
from app.schemas.employee import EmployeeBrief
from app.schemas.legal_entity import DepartmentBrief, LegalEntityBrief
from app.schemas.printer import PrinterBrief
from app.schemas.service_provider import ServiceProviderBrief


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    title: str
    kind: InvoiceLineKind
    target_raw: str
    qty: int
    price: Money
    total: Money
    cartridge_model: CartridgeModelBrief | None = None
    printer: PrinterBrief | None = None
    department: DepartmentBrief | None = None
    slots: list["InvoiceLineSlotRead"] = []
    skipped: bool
    applied: bool
    applied_note: str | None = None


class InvoiceLineSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    cartridge: CartridgeBrief | None = None
    department: DepartmentBrief | None = None
    applied: bool = False


class InvoiceLineSlotUpdate(BaseModel):
    cartridge_id: int | None = None
    department_id: int | None = None


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    issued_at: date
    supplier_name: str
    supplier_inn: str | None = None
    service_provider: ServiceProviderBrief | None = None
    buyer_name: str
    buyer_inn: str | None = None
    legal_entity: LegalEntityBrief | None = None
    department: DepartmentBrief | None = None
    holder_employee: EmployeeBrief | None = None
    total: Money
    vat: Money
    vat_rate: Money
    cost_with_vat: bool
    file_name: str
    status: InvoiceStatus
    sent_offset_days: int
    comment: str | None = None
    applied_at: datetime | None = None
    created_at: datetime
    lines: list[InvoiceLineRead] = []
    matched_lines: int = 0
    applied_lines: int = 0
    skipped_lines: int = 0


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    issued_at: date
    supplier_name: str
    buyer_name: str
    total: Money
    status: InvoiceStatus
    applied_at: datetime | None = None
    created_at: datetime
    lines_total: int = 0
    lines_matched: int = 0
    lines_applied: int = 0


class InvoiceUpdate(BaseModel):
    service_provider_id: int | None = None
    vat_rate: Money | None = Field(default=None, ge=0, le=100)
    cost_with_vat: bool | None = None
    legal_entity_id: int | None = None
    department_id: int | None = None
    holder_employee_id: int | None = None
    sent_offset_days: int | None = Field(default=None, ge=0, le=365)
    comment: str | None = None


class InvoiceLineUpdate(BaseModel):
    cartridge_model_id: int | None = None
    printer_id: int | None = None
    department_id: int | None = None
    cartridge_ids: list[int] | None = None
    skipped: bool | None = None


class InvoiceApplyResult(BaseModel):
    operations_created: int
    repairs_created: int
    cartridges_created: int
    applied_lines: int
    skipped_lines: int
    posted_cost: Money


InvoiceLineRead.model_rebuild()
