from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CartridgeColor, CartridgeKind
from app.models.part import part_printer_model
from app.models.types import cartridge_color_enum, cartridge_kind_enum

cartridge_model_printer_model = Table(
    "cartridge_model_printer_model",
    Base.metadata,
    Column(
        "cartridge_model_id",
        ForeignKey("cartridge_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "printer_model_id",
        ForeignKey("printer_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class PrinterModel(Base, TimestampMixin):
    __tablename__ = "printer_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)

    printers: Mapped[list["Printer"]] = relationship(back_populates="model")
    cartridge_models: Mapped[list["CartridgeModel"]] = relationship(
        secondary=cartridge_model_printer_model,
        back_populates="printer_models",
        lazy="selectin",
    )
    parts: Mapped[list["Part"]] = relationship(
        secondary=part_printer_model,
        back_populates="printer_models",
        lazy="selectin",
    )


class CartridgeModel(Base, TimestampMixin):
    __tablename__ = "cartridge_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(150), index=True)
    kind: Mapped[CartridgeKind] = mapped_column(
        cartridge_kind_enum, default=CartridgeKind.ORIGINAL, nullable=False
    )
    color: Mapped[CartridgeColor] = mapped_column(
        cartridge_color_enum, default=CartridgeColor.BLACK, nullable=False
    )
    resource_pages: Mapped[int | None] = mapped_column(Integer)
    refillable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    printer_models: Mapped[list[PrinterModel]] = relationship(
        secondary=cartridge_model_printer_model,
        back_populates="cartridge_models",
        lazy="selectin",
    )

    cartridges: Mapped[list["Cartridge"]] = relationship(back_populates="model")
