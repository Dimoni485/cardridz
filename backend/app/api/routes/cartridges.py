from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Cartridge, CartridgeModel, Operation, User
from app.models.enums import CartridgeStatus, OperationType
from app.schemas.cartridge import (
    CartridgeCreate,
    CartridgeRead,
    CartridgeUpdate,
    OperationCreate,
    OperationRead,
)
from app.schemas.common import Page
from app.services.cartridge_service import create_cartridge, perform_operation
from app.services.loaders import CARTRIDGE_LOADS, OPERATION_LOADS

router = APIRouter(prefix="/cartridges", tags=["cartridges"])


def _get_cartridge(db: Session, cartridge_id: int) -> Cartridge:
    cartridge = db.scalar(
        select(Cartridge)
        .options(*CARTRIDGE_LOADS)
        .where(Cartridge.id == cartridge_id)
    )
    if cartridge is None:
        raise HTTPException(status_code=404, detail="Картридж не найден")
    return cartridge


def _get_operation(db: Session, operation_id: int) -> Operation:
    return db.scalar(
        select(Operation)
        .options(*OPERATION_LOADS)
        .where(Operation.id == operation_id)
    )


@router.get("", response_model=Page[CartridgeRead])
def list_cartridges(
    q: str | None = None,
    status_filter: CartridgeStatus | None = Query(default=None, alias="status"),
    model_id: int | None = None,
    employee_id: int | None = None,
    printer_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Page[CartridgeRead]:
    stmt = select(Cartridge).options(*CARTRIDGE_LOADS)
    count_stmt = select(func.count(Cartridge.id))

    if q:
        pattern = f"%{q.strip()}%"
        condition = or_(
            Cartridge.inventory_no.ilike(pattern),
            Cartridge.serial_no.ilike(pattern),
            CartridgeModel.name.ilike(pattern),
            CartridgeModel.vendor.ilike(pattern),
        )
        stmt = stmt.join(Cartridge.model).where(condition)
        count_stmt = count_stmt.join(
            CartridgeModel, Cartridge.model_id == CartridgeModel.id
        ).where(condition)

    if status_filter is not None:
        stmt = stmt.where(Cartridge.status == status_filter)
        count_stmt = count_stmt.where(Cartridge.status == status_filter)
    if model_id is not None:
        stmt = stmt.where(Cartridge.model_id == model_id)
        count_stmt = count_stmt.where(Cartridge.model_id == model_id)
    if employee_id is not None:
        stmt = stmt.where(Cartridge.employee_id == employee_id)
        count_stmt = count_stmt.where(Cartridge.employee_id == employee_id)
    if printer_id is not None:
        stmt = stmt.where(Cartridge.printer_id == printer_id)
        count_stmt = count_stmt.where(Cartridge.printer_id == printer_id)

    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Cartridge.created_at.desc(), Cartridge.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.scalars(stmt).unique().all()
    return Page(items=list(items), total=total, skip=skip, limit=limit)


@router.post("", response_model=CartridgeRead, status_code=status.HTTP_201_CREATED)
def add_cartridge(
    data: CartridgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Cartridge:
    if db.get(CartridgeModel, data.model_id) is None:
        raise HTTPException(status_code=404, detail="Модель картриджа не найдена")
    if db.scalar(
        select(Cartridge.id).where(Cartridge.inventory_no == data.inventory_no)
    ):
        raise HTTPException(
            status_code=409, detail="Картридж с таким инвентарным номером уже существует"
        )

    cartridge = create_cartridge(
        db,
        inventory_no=data.inventory_no,
        serial_no=data.serial_no,
        model_id=data.model_id,
        purchase_price=data.purchase_price,
        purchase_date=data.purchase_date,
        notes=data.notes,
        comment=data.comment,
        user_id=current_user.id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Не удалось создать картридж: проверьте уникальность номера",
        ) from exc
    return _get_cartridge(db, cartridge.id)


@router.get("/{cartridge_id}", response_model=CartridgeRead)
def get_cartridge(cartridge_id: int, db: Session = Depends(get_db)) -> Cartridge:
    return _get_cartridge(db, cartridge_id)


@router.patch("/{cartridge_id}", response_model=CartridgeRead)
def update_cartridge(
    cartridge_id: int, data: CartridgeUpdate, db: Session = Depends(get_db)
) -> Cartridge:
    cartridge = _get_cartridge(db, cartridge_id)
    payload = data.model_dump(exclude_unset=True)

    inventory_no = payload.get("inventory_no")
    if inventory_no and inventory_no != cartridge.inventory_no:
        if db.scalar(
            select(Cartridge.id).where(
                Cartridge.inventory_no == inventory_no,
                Cartridge.id != cartridge_id,
            )
        ):
            raise HTTPException(
                status_code=409,
                detail="Картридж с таким инвентарным номером уже существует",
            )

    for field, value in payload.items():
        setattr(cartridge, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Не удалось сохранить изменения: проверьте уникальность номера",
        ) from exc
    db.expire(cartridge)
    return _get_cartridge(db, cartridge_id)


@router.delete("/{cartridge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cartridge(cartridge_id: int, db: Session = Depends(get_db)) -> Response:
    cartridge = _get_cartridge(db, cartridge_id)
    extra_operations = db.scalar(
        select(func.count(Operation.id)).where(
            Operation.cartridge_id == cartridge_id,
            Operation.type != OperationType.RECEIPT,
        )
    )
    if extra_operations:
        raise HTTPException(
            status_code=409,
            detail=(
                "У картриджа есть операции движения. Удаление невозможно — "
                "оформите списание."
            ),
        )
    db.delete(cartridge)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{cartridge_id}/operations", response_model=list[OperationRead])
def list_cartridge_operations(
    cartridge_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Operation]:
    _get_cartridge(db, cartridge_id)
    stmt = (
        select(Operation)
        .options(*OPERATION_LOADS)
        .where(Operation.cartridge_id == cartridge_id)
        .order_by(Operation.occurred_at.desc(), Operation.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).unique().all())


@router.post(
    "/{cartridge_id}/operations",
    response_model=OperationRead,
    status_code=status.HTTP_201_CREATED,
)
def add_cartridge_operation(
    cartridge_id: int,
    data: OperationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Operation:
    cartridge = _get_cartridge(db, cartridge_id)
    operation = perform_operation(db, cartridge, data, current_user.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Не удалось сохранить операцию"
        ) from exc
    return _get_operation(db, operation.id)
