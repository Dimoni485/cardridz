from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, TimestampMixin
from app.models.enums import CartridgeStatus, OperationType
from app.models.types import cartridge_status_enum, operation_type_enum


class Cartridge(Base, TimestampMixin):
    __tablename__ = "cartridges"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    serial_no: Mapped[str | None] = mapped_column(String(100))
    model_id: Mapped[int] = mapped_column(
        ForeignKey("cartridge_models.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[CartridgeStatus] = mapped_column(
        cartridge_status_enum,
        default=CartridgeStatus.IN_STOCK,
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    service_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_providers.id", ondelete="SET NULL"), index=True
    )
    service_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_return_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    refill_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    model: Mapped["CartridgeModel"] = relationship(back_populates="cartridges")
    employee: Mapped["Employee | None"] = relationship(back_populates="cartridges")
    printer: Mapped["Printer | None"] = relationship(back_populates="cartridges")
    service_provider: Mapped["ServiceProvider | None"] = relationship()
    operations: Mapped[list["Operation"]] = relationship(
        back_populates="cartridge",
        order_by="Operation.occurred_at.desc()",
        cascade="all, delete-orphan",
    )


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    cartridge_id: Mapped[int] = mapped_column(
        ForeignKey("cartridges.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[OperationType] = mapped_column(
        operation_type_enum, nullable=False, index=True
    )
    from_status: Mapped[CartridgeStatus | None] = mapped_column(
        cartridge_status_enum
    )
    to_status: Mapped[CartridgeStatus] = mapped_column(
        cartridge_status_enum, nullable=False
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    legal_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    service_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_providers.id", ondelete="SET NULL"), index=True
    )
    expected_return_date: Mapped[date | None] = mapped_column(Date)
    result: Mapped[str | None] = mapped_column(String(30))
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    document_no: Mapped[str | None] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    cartridge: Mapped[Cartridge] = relationship(back_populates="operations")
    employee: Mapped["Employee | None"] = relationship()
    printer: Mapped["Printer | None"] = relationship()
    legal_entity: Mapped["LegalEntity | None"] = relationship()
    department: Mapped["Department | None"] = relationship()
    service_provider: Mapped["ServiceProvider | None"] = relationship()
    user: Mapped["User | None"] = relationship()
