from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class LegalEntity(Base, TimestampMixin):
    __tablename__ = "legal_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    inn: Mapped[str | None] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    departments: Mapped[list["Department"]] = relationship(
        back_populates="legal_entity",
        order_by="Department.name",
        lazy="selectin",
    )


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("legal_entity_id", "name", name="uq_department_entity_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    legal_entity_id: Mapped[int] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), index=True)
    room: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    legal_entity: Mapped[LegalEntity] = relationship(back_populates="departments")
    employees: Mapped[list["Employee"]] = relationship(back_populates="department")
