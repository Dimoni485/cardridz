from sqlalchemy import Enum

from app.models.enums import (
    CartridgeColor,
    CartridgeKind,
    CartridgeStatus,
    InvoiceLineKind,
    InvoiceStatus,
    OperationType,
    PartKind,
    PartRequestStatus,
    PartUnitStatus,
    PrinterStatus,
)

ENUM_KWARGS = {"values_callable": lambda enum_cls: [item.value for item in enum_cls]}

cartridge_status_enum = Enum(
    CartridgeStatus, name="cartridge_status", **ENUM_KWARGS
)
operation_type_enum = Enum(OperationType, name="operation_type", **ENUM_KWARGS)
cartridge_kind_enum = Enum(CartridgeKind, name="cartridge_kind", **ENUM_KWARGS)
cartridge_color_enum = Enum(CartridgeColor, name="cartridge_color", **ENUM_KWARGS)
printer_status_enum = Enum(PrinterStatus, name="printer_status", **ENUM_KWARGS)
invoice_status_enum = Enum(InvoiceStatus, name="invoice_status", **ENUM_KWARGS)
invoice_line_kind_enum = Enum(
    InvoiceLineKind, name="invoice_line_kind", **ENUM_KWARGS
)
part_kind_enum = Enum(PartKind, name="part_kind", **ENUM_KWARGS)
part_unit_status_enum = Enum(
    PartUnitStatus, name="part_unit_status", **ENUM_KWARGS
)
part_request_status_enum = Enum(
    PartRequestStatus, name="part_request_status", **ENUM_KWARGS
)
