from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrinterStatus
from app.schemas.catalog import PrinterModelBrief
from app.schemas.employee import EmployeeBrief
from app.schemas.legal_entity import DepartmentBrief
from app.schemas.service_provider import ServiceProviderBrief


class PrinterBase(BaseModel):
    inventory_no: str = Field(min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=100)
    model_id: int
    location: str | None = Field(default=None, max_length=150)
    ip_address: str | None = Field(default=None, max_length=45)
    department_id: int | None = None
    employee_id: int | None = None
    status: PrinterStatus = PrinterStatus.ACTIVE
    notes: str | None = None


class PrinterCreate(PrinterBase):
    pass


class PrinterUpdate(BaseModel):
    inventory_no: str | None = Field(default=None, min_length=1, max_length=50)
    serial_no: str | None = Field(default=None, max_length=100)
    model_id: int | None = None
    location: str | None = Field(default=None, max_length=150)
    ip_address: str | None = Field(default=None, max_length=45)
    department_id: int | None = None
    employee_id: int | None = None
    status: PrinterStatus | None = None
    notes: str | None = None


class PrinterBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_no: str
    location: str | None = None
    department: DepartmentBrief | None = None
    model: PrinterModelBrief


class PrinterRead(PrinterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model: PrinterModelBrief
    department: DepartmentBrief | None = None
    employee: EmployeeBrief | None = None
    service_provider: ServiceProviderBrief | None = None
    service_since: datetime | None = None
    expected_return_date: date | None = None
    created_at: datetime
    updated_at: datetime
