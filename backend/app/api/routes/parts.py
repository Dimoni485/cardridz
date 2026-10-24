from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Part,
    PartInstallation,
    PartUnit,
    Printer,
    PrinterModel,
    User,
)
from app.models.enums import PartKind, PartUnitStatus, PrinterStatus
from app.schemas.part import (
    PartBrief,
    PartCreate,
    PartInstallationRead,
    PartInstallRequest,
    PartRead,
    PartRemoveRequest,
    PartUnitCreate,
    PartUnitRead,
    PartUnitUpdate,
    PartUpdate,
)
from app.schemas.printer import PrinterBrief

router = APIRouter(tags=["parts"])

UNIT_LOADS = (
    selectinload(PartUnit.part),
    selectinload(PartUnit.printer).selectinload(Printer.model),
    selectinload(PartUnit.installations),
)

INSTALLATION_LOADS = (
    selectinload(PartInstallation.unit).selectinload(PartUnit.part),
    selectinload(PartInstallation.printer).selectinload(Printer.model),
    selectinload(PartInstallation.user),
)


def _get_part(db: Session, part_id: int) -> Part:
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail="Запчасть не найдена")
    return part


def _get_unit(db: Session, unit_id: int) -> PartUnit:
    unit = db.scalar(
        select(PartUnit).options(*UNIT_LOADS).where(PartUnit.id == unit_id)
    )
    if unit is None:
        raise HTTPException(status_code=404, detail="Единица запчасти не найдена")
    return unit


def _unit_read(unit: PartUnit) -> PartUnitRead:
    payload = PartUnitRead.model_validate(unit)
    open_install = next(
        (item for item in unit.installations if item.removed_at is None), None
    )
    payload.installed_at = open_install.installed_at if open_install else None
    return payload


def _installation_read(item: PartInstallation) -> PartInstallationRead:
    return PartInstallationRead(
        id=item.id,
        unit_id=item.unit_id,
        part=PartBrief.model_validate(item.unit.part),
        inventory_no=item.unit.inventory_no,
        printer=(
            PrinterBrief.model_validate(item.printer) if item.printer else None
        ),
        installed_at=item.installed_at,
        removed_at=item.removed_at,
        comment=item.comment,
        user=item.user,
        needs_replacement=item.removed_at is None
        and item.unit.needs_replacement,
    )


def _parts_read(db: Session, parts: list[Part]) -> list[PartRead]:
    counts: dict[int, dict[PartUnitStatus, int]] = {}
    for part_id, unit_status, total in db.execute(
        select(PartUnit.part_id, PartUnit.status, func.count()).group_by(
            PartUnit.part_id, PartUnit.status
        )
    ):
        counts.setdefault(part_id, {})[unit_status] = total
    attention = dict(
        db.execute(
            select(PartUnit.part_id, func.count())
            .where(
                PartUnit.needs_replacement.is_(True),
                PartUnit.status == PartUnitStatus.INSTALLED,
            )
            .group_by(PartUnit.part_id)
        ).all()
    )

    result = []
    for part in parts:
        payload = PartRead.model_validate(part)
        by_status = counts.get(part.id, {})
        payload.units_in_stock = by_status.get(PartUnitStatus.IN_STOCK, 0)
        payload.units_installed = by_status.get(PartUnitStatus.INSTALLED, 0)
        payload.units_total = sum(by_status.values())
        payload.needs_replacement = attention.get(part.id, 0)
        result.append(payload)
    return result


def _resolve_printer_models(
    db: Session, printer_model_ids: list[int]
) -> list[PrinterModel]:
    unique_ids = list(dict.fromkeys(printer_model_ids))
    if not unique_ids:
        return []
    models = list(
        db.scalars(select(PrinterModel).where(PrinterModel.id.in_(unique_ids))).all()
    )
    if len(models) != len(unique_ids):
        raise HTTPException(
            status_code=400, detail="Некоторые модели принтеров не найдены"
        )
    return models


@router.get("/parts", response_model=list[PartRead])
def list_parts(
    q: str | None = None,
    kind: PartKind | None = None,
    db: Session = Depends(get_db),
) -> list[PartRead]:
    stmt = select(Part).order_by(Part.name)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Part.name.ilike(pattern),
                Part.vendor.ilike(pattern),
                Part.article.ilike(pattern),
            )
        )
    if kind is not None:
        stmt = stmt.where(Part.kind == kind)
    return _parts_read(db, list(db.scalars(stmt).all()))


@router.post("/parts", response_model=PartRead, status_code=status.HTTP_201_CREATED)
def create_part(data: PartCreate, db: Session = Depends(get_db)) -> PartRead:
    printer_models = _resolve_printer_models(db, data.printer_model_ids)
    part = Part(**data.model_dump(exclude={"printer_model_ids"}))
    part.printer_models = printer_models
    db.add(part)
    db.commit()
    db.refresh(part)
    return _parts_read(db, [part])[0]


@router.get("/parts/{part_id}", response_model=PartRead)
def get_part(part_id: int, db: Session = Depends(get_db)) -> PartRead:
    return _parts_read(db, [_get_part(db, part_id)])[0]


@router.patch("/parts/{part_id}", response_model=PartRead)
def update_part(
    part_id: int, data: PartUpdate, db: Session = Depends(get_db)
) -> PartRead:
    part = _get_part(db, part_id)
    payload = data.model_dump(exclude_unset=True)
    printer_model_ids = payload.pop("printer_model_ids", None)
    for field, value in payload.items():
        setattr(part, field, value)
    if printer_model_ids is not None:
        part.printer_models = _resolve_printer_models(db, printer_model_ids)
    db.commit()
    db.refresh(part)
    return _parts_read(db, [part])[0]


@router.delete("/parts/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part(part_id: int, db: Session = Depends(get_db)) -> Response:
    part = _get_part(db, part_id)
    units = db.scalar(
        select(func.count()).select_from(PartUnit).where(PartUnit.part_id == part.id)
    )
    if units:
        raise HTTPException(
            status_code=409,
            detail="У запчасти есть единицы учёта — удаление невозможно",
        )
    db.delete(part)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/part-units", response_model=list[PartUnitRead])
def list_units(
    part_id: int | None = None,
    status_filter: PartUnitStatus | None = None,
    printer_id: int | None = None,
    needs_replacement: bool | None = None,
    db: Session = Depends(get_db),
) -> list[PartUnitRead]:
    stmt = select(PartUnit).options(*UNIT_LOADS).order_by(PartUnit.inventory_no)
    if part_id is not None:
        stmt = stmt.where(PartUnit.part_id == part_id)
    if status_filter is not None:
        stmt = stmt.where(PartUnit.status == status_filter)
    if printer_id is not None:
        stmt = stmt.where(PartUnit.printer_id == printer_id)
    if needs_replacement is not None:
        stmt = stmt.where(PartUnit.needs_replacement.is_(needs_replacement))
    return [_unit_read(unit) for unit in db.scalars(stmt).unique().all()]


@router.post(
    "/parts/{part_id}/units",
    response_model=PartUnitRead,
    status_code=status.HTTP_201_CREATED,
)
def create_unit(
    part_id: int, data: PartUnitCreate, db: Session = Depends(get_db)
) -> PartUnitRead:
    part = _get_part(db, part_id)
    if db.scalar(
        select(PartUnit.id).where(PartUnit.inventory_no == data.inventory_no)
    ):
        raise HTTPException(
            status_code=409,
            detail="Запчасть с таким инвентарным номером уже существует",
        )
    unit = PartUnit(part_id=part.id, **data.model_dump())
    db.add(unit)
    db.commit()
    return _unit_read(_get_unit(db, unit.id))


@router.patch("/part-units/{unit_id}", response_model=PartUnitRead)
def update_unit(
    unit_id: int, data: PartUnitUpdate, db: Session = Depends(get_db)
) -> PartUnitRead:
    unit = _get_unit(db, unit_id)
    payload = data.model_dump(exclude_unset=True)
    inventory_no = payload.get("inventory_no")
    if inventory_no and inventory_no != unit.inventory_no:
        if db.scalar(
            select(PartUnit.id).where(
                PartUnit.inventory_no == inventory_no, PartUnit.id != unit.id
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="Запчасть с таким инвентарным номером уже существует",
            )
    for field, value in payload.items():
        setattr(unit, field, value)
    db.commit()
    return _unit_read(_get_unit(db, unit_id))


@router.delete("/part-units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: int, db: Session = Depends(get_db)) -> Response:
    unit = _get_unit(db, unit_id)
    if unit.status == PartUnitStatus.INSTALLED:
        raise HTTPException(
            status_code=409, detail="Запчасть установлена — сначала снимите её"
        )
    if unit.installations:
        raise HTTPException(
            status_code=409,
            detail="У запчасти есть история замен — удаление невозможно",
        )
    db.delete(unit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/part-units/{unit_id}/install", response_model=PartUnitRead)
def install_unit(
    unit_id: int,
    data: PartInstallRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartUnitRead:
    unit = _get_unit(db, unit_id)
    if unit.status != PartUnitStatus.IN_STOCK:
        raise HTTPException(
            status_code=409, detail="Запчасть не находится на складе"
        )
    printer = db.get(Printer, data.printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Принтер не найден")
    if printer.status == PrinterStatus.RETIRED:
        raise HTTPException(
            status_code=409, detail="Принтер списан — установка невозможна"
        )

    installation = PartInstallation(
        printer_id=printer.id,
        comment=data.comment,
        user_id=current_user.id,
        installed_at=datetime.now().astimezone(),
    )
    unit.installations.append(installation)
    unit.status = PartUnitStatus.INSTALLED
    unit.printer_id = printer.id
    unit.printer = printer
    unit.needs_replacement = False
    db.commit()
    return _unit_read(_get_unit(db, unit.id))


@router.post("/part-units/{unit_id}/remove", response_model=PartUnitRead)
def remove_unit(
    unit_id: int,
    data: PartRemoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartUnitRead:
    unit = _get_unit(db, unit_id)
    if unit.status != PartUnitStatus.INSTALLED:
        raise HTTPException(status_code=409, detail="Запчасть не установлена")

    open_install = next(
        (item for item in unit.installations if item.removed_at is None), None
    )
    if open_install is not None:
        open_install.removed_at = datetime.now().astimezone()
        if data.comment:
            open_install.comment = (
                f"{open_install.comment}; {data.comment}"
                if open_install.comment
                else data.comment
            )
    unit.status = (
        PartUnitStatus.WRITTEN_OFF if data.write_off else PartUnitStatus.IN_STOCK
    )
    unit.printer_id = None
    unit.printer = None
    unit.needs_replacement = False
    db.commit()
    return _unit_read(_get_unit(db, unit.id))


@router.get("/part-installations", response_model=list[PartInstallationRead])
def list_installations(
    printer_id: int | None = None,
    part_id: int | None = None,
    open_only: bool = False,
    needs_replacement: bool | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[PartInstallationRead]:
    stmt = (
        select(PartInstallation)
        .options(*INSTALLATION_LOADS)
        .order_by(PartInstallation.installed_at.desc(), PartInstallation.id.desc())
        .limit(limit)
    )
    if printer_id is not None:
        stmt = stmt.where(PartInstallation.printer_id == printer_id)
    if part_id is not None:
        stmt = stmt.join(PartUnit, PartUnit.id == PartInstallation.unit_id).where(
            PartUnit.part_id == part_id
        )
    if open_only:
        stmt = stmt.where(PartInstallation.removed_at.is_(None))
    if needs_replacement is not None:
        stmt = stmt.join(
            PartUnit, PartUnit.id == PartInstallation.unit_id
        ).where(PartUnit.needs_replacement.is_(needs_replacement))
    items = db.scalars(stmt).unique().all()
    return [_installation_read(item) for item in items]
