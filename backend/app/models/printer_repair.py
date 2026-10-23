from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import PrinterRepairStatus


class PrinterRepair(Base, TimestampMixin):
    __tablename__ = "printer_repairs"

    id: Mapped[int] = mapped_column(primary_key=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="RESTRICT"), index=True
    )
    service_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_providers.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=PrinterRepairStatus.IN_SERVICE.value, nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_return_date: Mapped[date | None] = mapped_column(Date)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_no: Mapped[str | None] = mapped_column(String(100))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    result: Mapped[str | None] = mapped_column(String(30))
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL")
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    printer: Mapped["Printer"] = relationship(back_populates="repairs")
    service_provider: Mapped["ServiceProvider | None"] = relationship()
    legal_entity: Mapped["LegalEntity | None"] = relationship()
    department: Mapped["Department | None"] = relationship()
    user: Mapped["User | None"] = relationship()
