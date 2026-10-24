from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PartKind, PartRequestStatus, PartUnitStatus
from app.schemas.auth import UserBrief
from app.schemas.catalog import PrinterModelBrief
from app.schemas.common import Money
from app.schemas.printer import PrinterBrief


class PartBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    kind: PartKind = PartKind.OTHER
    vendor: str | None = Field(default=None, max_length=100)
    article: str | None = Field(default=None, max_length=100)
    min_stock: int = Field(default=0, ge=0)
    notes: str | None = None
    is_active: bool = True


class PartCreate(PartBase):
    printer_model_ids: list[int] = []


class PartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    kind: PartKind | None = None
    vendor: str | None = Field(default=None, max_length=100)
    article: str | None = Field(default=None, max_length=100)
    min_stock: int | None = Field(default=None, ge=0)
    notes: str | None = None
    is_active: bool | None = None
    printer_model_ids: list[int] | None = None


class PartBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: PartKind
    vendor: str | None = None
    article: str | None = None


class PartRead(PartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    printer_models: list[PrinterModelBrief] = []
    units_total: int = 0
    units_in_stock: int = 0
    units_installed: int = 0
    needs_replacement: int = 0
    created_at: datetime
    updated_at: datetime


class PartUnitCreate(BaseModel):
    inventory_no: str = Field(min_length=1, max_length=50)
    purchase_price: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None


class PartUnitUpdate(BaseModel):
    inventory_no: str | None = Field(default=None, min_length=1, max_length=50)
    needs_replacement: bool | None = None
    purchase_price: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None


class PartUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_no: str
    status: PartUnitStatus
    part: PartBrief
    printer: PrinterBrief | None = None
    needs_replacement: bool
    purchase_price: Money | None = None
    purchase_date: date | None = None
    notes: str | None = None
    installed_at: datetime | None = None
    created_at: datetime


class PartInstallRequest(BaseModel):
    printer_id: int
    comment: str | None = None


class PartRemoveRequest(BaseModel):
    write_off: bool = False
    comment: str | None = None


class PartInstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: int
    part: PartBrief
    inventory_no: str
    printer: PrinterBrief | None = None
    installed_at: datetime
    removed_at: datetime | None = None
    comment: str | None = None
    user: UserBrief | None = None
    needs_replacement: bool = False


class PartRequestLineCreate(BaseModel):
    part_id: int
    qty: int = Field(default=1, ge=1)
    note: str | None = None


class PartRequestCreate(BaseModel):
    printer_id: int
    needed_by: date | None = None
    comment: str | None = None
    lines: list[PartRequestLineCreate] = Field(min_length=1)


class PartRequestUpdate(BaseModel):
    printer_id: int | None = None
    needed_by: date | None = None
    comment: str | None = None
    lines: list[PartRequestLineCreate] | None = None


class PartRequestLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part: PartBrief
    qty: int
    note: str | None = None


class PartRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    printer: PrinterBrief | None = None
    status: PartRequestStatus
    needed_by: date | None = None
    comment: str | None = None
    created_by: UserBrief | None = None
    submitted_at: datetime | None = None
    ordered_at: datetime | None = None
    received_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    lines: list[PartRequestLineRead] = []
