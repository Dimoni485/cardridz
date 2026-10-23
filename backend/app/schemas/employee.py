from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.legal_entity import DepartmentBrief


class EmployeeBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    department_id: int | None = None
    position: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    department_id: int | None = None
    position: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class EmployeeRead(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: DepartmentBrief | None = None
    created_at: datetime
    updated_at: datetime


class EmployeeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    position: str | None = None
    department: DepartmentBrief | None = None
