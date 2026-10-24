from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import PartKind, PartRequestStatus, PartUnitStatus
from app.models.types import (
    part_kind_enum,
    part_request_status_enum,
    part_unit_status_enum,
)

part_printer_model = Table(
    "part_printer_model",
    Base.metadata,
    Column(
        "part_id",
        ForeignKey("parts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "printer_model_id",
        ForeignKey("printer_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Part(Base, TimestampMixin):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    kind: Mapped[PartKind] = mapped_column(
        part_kind_enum, default=PartKind.OTHER, nullable=False
    )
    vendor: Mapped[str | None] = mapped_column(String(100))
    article: Mapped[str | None] = mapped_column(String(100))
    min_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    printer_models: Mapped[list["PrinterModel"]] = relationship(
        secondary=part_printer_model,
        back_populates="parts",
        lazy="selectin",
    )
    units: Mapped[list["PartUnit"]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )


class PartUnit(Base, TimestampMixin):
    __tablename__ = "part_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[PartUnitStatus] = mapped_column(
        part_unit_status_enum, default=PartUnitStatus.IN_STOCK, nullable=False,
        index=True,
    )
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    needs_replacement: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    part: Mapped["Part"] = relationship(back_populates="units")
    printer: Mapped["Printer | None"] = relationship()
    installations: Mapped[list["PartInstallation"]] = relationship(
        back_populates="unit",
        order_by="PartInstallation.installed_at.desc()",
        cascade="all, delete-orphan",
    )


class PartInstallation(Base):
    __tablename__ = "part_installations"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("part_units.id", ondelete="CASCADE"), index=True
    )
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    unit: Mapped["PartUnit"] = relationship(back_populates="installations")
    printer: Mapped["Printer | None"] = relationship()
    user: Mapped["User | None"] = relationship()


class PartRequest(Base, TimestampMixin):
    __tablename__ = "part_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[PartRequestStatus] = mapped_column(
        part_request_status_enum,
        default=PartRequestStatus.DRAFT,
        nullable=False,
        index=True,
    )
    needed_by: Mapped[date | None] = mapped_column(Date)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    printer: Mapped["Printer | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    lines: Mapped[list["PartRequestLine"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class PartRequestLine(Base):
    __tablename__ = "part_request_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("part_requests.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), index=True
    )
    qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    request: Mapped["PartRequest"] = relationship(back_populates="lines")
    part: Mapped["Part"] = relationship()
