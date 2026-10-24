from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import InvoiceLineKind, InvoiceStatus
from app.models.types import invoice_line_kind_enum, invoice_status_enum


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("number", "issued_at", name="uq_invoices_number_issued_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), index=True)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255))
    supplier_inn: Mapped[str | None] = mapped_column(String(12), index=True)
    service_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_providers.id", ondelete="SET NULL"), index=True
    )
    buyer_name: Mapped[str] = mapped_column(String(255))
    buyer_inn: Mapped[str | None] = mapped_column(String(12), index=True)
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    holder_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, nullable=False
    )
    cost_with_vat: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[InvoiceStatus] = mapped_column(
        invoice_status_enum, default=InvoiceStatus.DRAFT, nullable=False, index=True
    )
    sent_offset_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    service_provider: Mapped["ServiceProvider | None"] = relationship()
    legal_entity: Mapped["LegalEntity | None"] = relationship()
    department: Mapped["Department | None"] = relationship()
    holder_employee: Mapped["Employee | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        order_by="InvoiceLine.number",
        cascade="all, delete-orphan",
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[InvoiceLineKind] = mapped_column(
        invoice_line_kind_enum, nullable=False
    )
    target_raw: Mapped[str] = mapped_column(String(150))
    qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    cartridge_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("cartridge_models.id", ondelete="SET NULL"), index=True
    )
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_note: Mapped[str | None] = mapped_column(String(255))

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
    slots: Mapped[list["InvoiceLineSlot"]] = relationship(
        back_populates="line",
        order_by="InvoiceLineSlot.position",
        cascade="all, delete-orphan",
    )
    cartridge_model: Mapped["CartridgeModel | None"] = relationship()
    printer: Mapped["Printer | None"] = relationship()
    department: Mapped["Department | None"] = relationship()


class InvoiceLineSlot(Base):
    __tablename__ = "invoice_line_slots"
    __table_args__ = (
        UniqueConstraint("line_id", "position", name="uq_invoice_line_slots_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("invoice_lines.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    cartridge_id: Mapped[int | None] = mapped_column(
        ForeignKey("cartridges.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    line: Mapped["InvoiceLine"] = relationship(back_populates="slots")
    cartridge: Mapped["Cartridge | None"] = relationship()
    department: Mapped["Department | None"] = relationship()
