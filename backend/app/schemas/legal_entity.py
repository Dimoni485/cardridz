from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LegalEntityBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inn: str | None = Field(default=None, max_length=12)
    is_active: bool = True
    notes: str | None = None


class LegalEntityCreate(LegalEntityBase):
    pass


class LegalEntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    inn: str | None = Field(default=None, max_length=12)
    is_active: bool | None = None
    notes: str | None = None


class LegalEntityBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DepartmentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    room: str | None = None
    legal_entity: LegalEntityBrief


class DepartmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    room: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    legal_entity_id: int


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    room: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    legal_entity_id: int | None = None


class DepartmentRead(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_entity_id: int
    legal_entity: LegalEntityBrief
    created_at: datetime
    updated_at: datetime


class LegalEntityRead(LegalEntityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departments: list[DepartmentBrief] = []
    created_at: datetime
    updated_at: datetime
