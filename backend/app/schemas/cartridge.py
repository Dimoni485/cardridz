from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CartridgeStatus, OperationType, ServiceResult
from app.schemas.auth import UserBrief
from app.schemas.catalog import CartridgeModelBrief
from app.schemas.common import Money
from app.schemas.employee import EmployeeBrief
from app.schemas.legal_entity import DepartmentBrief, LegalEntityBrief
from app.schemas.printer import PrinterBrief
from app.schemas.service_provider import ServiceProviderBrief


class CartridgeCreate(BaseModel):
    inventory_no: str = Field(min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=100)
    model_id: int
    purchase_price: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None
    comment: str | None = None


class CartridgeUpdate(BaseModel):
    inventory_no: str | None = Field(default=None, min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=100)
    purchase_price: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None


class CartridgeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_no: str
    model: CartridgeModelBrief


class CartridgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_no: str
    serial_no: str | None = None
    status: CartridgeStatus
    model: CartridgeModelBrief
    employee: EmployeeBrief | None = None
    printer: PrinterBrief | None = None
    service_provider: ServiceProviderBrief | None = None
    service_since: datetime | None = None
    expected_return_date: date | None = None
    purchase_price: Money | None = None
    purchase_date: date | None = None
    refill_count: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class OperationCreate(BaseModel):
    type: OperationType
    employee_id: int | None = None
    printer_id: int | None = None
    service_provider_id: int | None = None
    expected_return_date: date | None = None
    result: ServiceResult | None = None
    cost: Money | None = Field(default=None, ge=0)
    document_no: str | None = Field(default=None, max_length=100)
    comment: str | None = None
    occurred_at: datetime | None = None


class OperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cartridge_id: int
    cartridge: CartridgeBrief
    type: OperationType
    from_status: CartridgeStatus | None = None
    to_status: CartridgeStatus
    employee: EmployeeBrief | None = None
    printer: PrinterBrief | None = None
    legal_entity: LegalEntityBrief | None = None
    department: DepartmentBrief | None = None
    service_provider: ServiceProviderBrief | None = None
    expected_return_date: date | None = None
    result: ServiceResult | None = None
    user: UserBrief | None = None
    cost: Money | None = None
    document_no: str | None = None
    comment: str | None = None
    occurred_at: datetime
