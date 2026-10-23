from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inn: str | None = Field(default=None, max_length=12)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool = True


class ServiceProviderCreate(ServiceProviderBase):
    pass


class ServiceProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    inn: str | None = Field(default=None, max_length=12)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool | None = None


class ServiceProviderRead(ServiceProviderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ServiceProviderBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
