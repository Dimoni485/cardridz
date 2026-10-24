from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class CartridgeStatus(str, Enum):
    IN_STOCK = "in_stock"
    ISSUED = "issued"
    INSTALLED = "installed"
    IN_REFILL = "in_refill"
    IN_RESTORE = "in_restore"
    WRITTEN_OFF = "written_off"


class CartridgeKind(str, Enum):
    ORIGINAL = "original"
    COMPATIBLE = "compatible"


class CartridgeColor(str, Enum):
    BLACK = "black"
    CYAN = "cyan"
    MAGENTA = "magenta"
    YELLOW = "yellow"
    OTHER = "other"


class PrinterStatus(str, Enum):
    ACTIVE = "active"
    REPAIR = "repair"
    RETIRED = "retired"


class ServiceResult(str, Enum):
    REFILLED = "refilled"
    RESTORED = "restored"
    REPAIRED = "repaired"
    FAILED = "failed"
    UNREPAIRABLE = "unrepairable"
    OTHER = "other"


class PrinterRepairStatus(str, Enum):
    IN_SERVICE = "in_service"
    RETURNED = "returned"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    APPLIED = "applied"


class InvoiceLineKind(str, Enum):
    RESTORE = "restore"
    REFILL = "refill"
    REPAIR = "repair"


class OperationType(str, Enum):
    RECEIPT = "receipt"
    ISSUE = "issue"
    INSTALL = "install"
    UNINSTALL = "uninstall"
    RETURN = "return"
    SEND_REFILL = "send_refill"
    REFILL_DONE = "refill_done"
    SEND_RESTORE = "send_restore"
    RESTORE_DONE = "restore_done"
    WRITE_OFF = "write_off"
