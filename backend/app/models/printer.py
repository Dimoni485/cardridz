from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import PrinterStatus
from app.models.types import printer_status_enum


class Printer(Base, TimestampMixin):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    serial_no: Mapped[str | None] = mapped_column(String(100))
    model_id: Mapped[int] = mapped_column(
        ForeignKey("printer_models.id", ondelete="RESTRICT"), index=True
    )
    location: Mapped[str | None] = mapped_column(String(150))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL")
    )
    status: Mapped[PrinterStatus] = mapped_column(
        printer_status_enum, default=PrinterStatus.ACTIVE, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    service_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_providers.id", ondelete="SET NULL"), index=True
    )
    service_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_return_date: Mapped[date | None] = mapped_column(Date)

    model: Mapped["PrinterModel"] = relationship(back_populates="printers")
    employee: Mapped["Employee | None"] = relationship(back_populates="printers")
    department: Mapped["Department | None"] = relationship()
    cartridges: Mapped[list["Cartridge"]] = relationship(back_populates="printer")
    service_provider: Mapped["ServiceProvider | None"] = relationship()
    repairs: Mapped[list["PrinterRepair"]] = relationship(
        back_populates="printer",
        order_by="PrinterRepair.sent_at.desc()",
        cascade="all, delete-orphan",
    )
