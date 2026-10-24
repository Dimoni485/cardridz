from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Part, PartRequest, PartRequestLine, Printer, User
from app.models.enums import PartRequestStatus
from app.schemas.part import (
    PartRequestCreate,
    PartRequestRead,
    PartRequestUpdate,
)

router = APIRouter(prefix="/part-requests", tags=["part-requests"])

REQUEST_LOADS = (
    selectinload(PartRequest.printer).selectinload(Printer.model),
    selectinload(PartRequest.created_by),
    selectinload(PartRequest.lines).selectinload(PartRequestLine.part),
)


def _get_request(db: Session, request_id: int) -> PartRequest:
    request = db.scalar(
        select(PartRequest)
        .options(*REQUEST_LOADS)
        .where(PartRequest.id == request_id)
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request


def _resolve_printer(db: Session, printer_id: int) -> Printer:
    printer = db.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Принтер не найден")
    return printer


def _build_lines(
    db: Session, lines: list
) -> list[PartRequestLine]:
    prepared = []
    for line in lines:
        part = db.get(Part, line.part_id)
        if part is None:
            raise HTTPException(
                status_code=404,
                detail=f"Запчасть id={line.part_id} не найдена",
            )
        prepared.append(
            PartRequestLine(part_id=part.id, qty=line.qty, note=line.note)
        )
    return prepared


def _set_status(
    request: PartRequest, new_status: PartRequestStatus
) -> None:
    if request.status == new_status:
        raise HTTPException(status_code=409, detail="Заявка уже в этом статусе")
    now = datetime.now().astimezone()
    if new_status == PartRequestStatus.SUBMITTED:
        request.submitted_at = now
    elif new_status == PartRequestStatus.ORDERED:
        request.ordered_at = now
    elif new_status == PartRequestStatus.RECEIVED:
        request.received_at = now
    elif new_status == PartRequestStatus.CANCELLED:
        request.cancelled_at = now
    request.status = new_status


@router.get("", response_model=list[PartRequestRead])
def list_requests(
    status_filter: PartRequestStatus | None = None,
    printer_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[PartRequest]:
    stmt = select(PartRequest).options(*REQUEST_LOADS)
    if status_filter is not None:
        stmt = stmt.where(PartRequest.status == status_filter)
    if printer_id is not None:
        stmt = stmt.where(PartRequest.printer_id == printer_id)
    stmt = stmt.order_by(PartRequest.created_at.desc(), PartRequest.id.desc())
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=PartRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    data: PartRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartRequest:
    printer = _resolve_printer(db, data.printer_id)
    request = PartRequest(
        number="",
        printer_id=printer.id,
        status=PartRequestStatus.DRAFT,
        needed_by=data.needed_by,
        comment=data.comment,
        created_by_id=current_user.id,
    )
    request.lines = _build_lines(db, data.lines)
    db.add(request)
    db.flush()
    request.number = f"ЗЧ-{request.id:04d}"
    db.commit()
    return _get_request(db, request.id)


@router.get("/{request_id}", response_model=PartRequestRead)
def get_request(request_id: int, db: Session = Depends(get_db)) -> PartRequest:
    return _get_request(db, request_id)


@router.patch("/{request_id}", response_model=PartRequestRead)
def update_request(
    request_id: int, data: PartRequestUpdate, db: Session = Depends(get_db)
) -> PartRequest:
    request = _get_request(db, request_id)
    if request.status != PartRequestStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail="Изменять можно только черновик заявки"
        )
    payload = data.model_dump(exclude_unset=True)
    lines = payload.pop("lines", None)
    printer_id = payload.pop("printer_id", None)
    if printer_id is not None:
        printer = _resolve_printer(db, printer_id)
        request.printer_id = printer.id
    for field, value in payload.items():
        setattr(request, field, value)
    if lines is not None:
        request.lines = _build_lines(db, data.lines or [])
    db.commit()
    return _get_request(db, request.id)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: int, db: Session = Depends(get_db)) -> Response:
    request = _get_request(db, request_id)
    if request.status != PartRequestStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail="Удалить можно только черновик заявки"
        )
    db.delete(request)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{request_id}/submit", response_model=PartRequestRead)
def submit_request(request_id: int, db: Session = Depends(get_db)) -> PartRequest:
    request = _get_request(db, request_id)
    if request.status != PartRequestStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Отправить можно только черновик")
    _set_status(request, PartRequestStatus.SUBMITTED)
    db.commit()
    return _get_request(db, request_id)


@router.post("/{request_id}/order", response_model=PartRequestRead)
def order_request(request_id: int, db: Session = Depends(get_db)) -> PartRequest:
    request = _get_request(db, request_id)
    if request.status != PartRequestStatus.SUBMITTED:
        raise HTTPException(
            status_code=409, detail="Заказать можно только отправленную заявку"
        )
    _set_status(request, PartRequestStatus.ORDERED)
    db.commit()
    return _get_request(db, request_id)


@router.post("/{request_id}/receive", response_model=PartRequestRead)
def receive_request(request_id: int, db: Session = Depends(get_db)) -> PartRequest:
    request = _get_request(db, request_id)
    if request.status != PartRequestStatus.ORDERED:
        raise HTTPException(
            status_code=409, detail="Получить можно только заказанную заявку"
        )
    _set_status(request, PartRequestStatus.RECEIVED)
    db.commit()
    return _get_request(db, request_id)


@router.post("/{request_id}/cancel", response_model=PartRequestRead)
def cancel_request(request_id: int, db: Session = Depends(get_db)) -> PartRequest:
    request = _get_request(db, request_id)
    if request.status in {
        PartRequestStatus.RECEIVED,
        PartRequestStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=409, detail="Эту заявку отменить нельзя"
        )
    _set_status(request, PartRequestStatus.CANCELLED)
    db.commit()
    return _get_request(db, request_id)
