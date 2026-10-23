from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import local_day_start
from app.db.session import get_db
from app.models import Operation
from app.models.enums import OperationType
from app.schemas.cartridge import OperationRead
from app.schemas.common import Page
from app.services.loaders import OPERATION_LOADS

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=Page[OperationRead])
def list_operations(
    type_filter: OperationType | None = Query(default=None, alias="type"),
    cartridge_id: int | None = None,
    employee_id: int | None = None,
    printer_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Page[OperationRead]:
    stmt = select(Operation).options(*OPERATION_LOADS)
    count_stmt = select(func.count(Operation.id))

    filters = []
    if type_filter is not None:
        filters.append(Operation.type == type_filter)
    if cartridge_id is not None:
        filters.append(Operation.cartridge_id == cartridge_id)
    if employee_id is not None:
        filters.append(Operation.employee_id == employee_id)
    if printer_id is not None:
        filters.append(Operation.printer_id == printer_id)
    if date_from is not None:
        filters.append(Operation.occurred_at >= local_day_start(date_from))
    if date_to is not None:
        filters.append(
            Operation.occurred_at < local_day_start(date_to + timedelta(days=1))
        )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Дата начала позже даты окончания")

    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Operation.occurred_at.desc(), Operation.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.scalars(stmt).unique().all()
    return Page(items=list(items), total=total, skip=skip, limit=limit)
