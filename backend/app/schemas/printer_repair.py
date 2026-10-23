from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrinterRepairStatus, ServiceResult
from app.schemas.auth import UserBrief
from app.schemas.common import Money
from app.schemas.legal_entity import DepartmentBrief, LegalEntityBrief
from app.schemas.service_provider import ServiceProviderBrief


class PrinterRepairCreate(BaseModel):
    service_provider_id: int
    sent_at: datetime | None = None
    expected_return_date: date | None = None
    document_no: str | None = Field(default=None, max_length=100)
    comment: str | None = None


class PrinterRepairClose(BaseModel):
    returned_at: datetime | None = None
    cost: Money | None = Field(default=None, ge=0)
    result: ServiceResult
    document_no: str | None = Field(default=None, max_length=100)
    comment: str | None = None


class PrinterRepairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    printer_id: int
    status: PrinterRepairStatus
    sent_at: datetime
    expected_return_date: date | None = None
    returned_at: datetime | None = None
    document_no: str | None = None
    cost: Money | None = None
    result: ServiceResult | None = None
    service_provider: ServiceProviderBrief | None = None
    legal_entity: LegalEntityBrief | None = None
    department: DepartmentBrief | None = None
    user: UserBrief | None = None
    comment: str | None = None
    created_at: datetime
