from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CartridgeColor, CartridgeKind


class PrinterModelBase(BaseModel):
    vendor: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    notes: str | None = None


class PrinterModelCreate(PrinterModelBase):
    pass


class PrinterModelUpdate(BaseModel):
    vendor: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    notes: str | None = None


class PrinterModelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor: str
    name: str


class PrinterModelRead(PrinterModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CartridgeModelBase(BaseModel):
    vendor: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    kind: CartridgeKind = CartridgeKind.ORIGINAL
    color: CartridgeColor = CartridgeColor.BLACK
    resource_pages: int | None = Field(default=None, ge=0)
    refillable: bool = True
    min_stock: int = Field(default=0, ge=0)
    notes: str | None = None


class CartridgeModelCreate(CartridgeModelBase):
    printer_model_ids: list[int] = []


class CartridgeModelUpdate(BaseModel):
    vendor: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    kind: CartridgeKind | None = None
    color: CartridgeColor | None = None
    resource_pages: int | None = Field(default=None, ge=0)
    refillable: bool | None = None
    min_stock: int | None = Field(default=None, ge=0)
    notes: str | None = None
    printer_model_ids: list[int] | None = None


class CartridgeModelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor: str
    name: str
    color: CartridgeColor
    kind: CartridgeKind
    refillable: bool


class CartridgeModelRead(CartridgeModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    printer_models: list[PrinterModelBrief] = []
    created_at: datetime
    updated_at: datetime
