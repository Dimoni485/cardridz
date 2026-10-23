from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Printer, PrinterModel
from app.schemas.catalog import (
    PrinterModelCreate,
    PrinterModelRead,
    PrinterModelUpdate,
)

router = APIRouter(prefix="/printer-models", tags=["printer-models"])


def _get_printer_model(db: Session, model_id: int) -> PrinterModel:
    model = db.get(PrinterModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Модель принтера не найдена")
    return model


@router.get("", response_model=list[PrinterModelRead])
def list_printer_models(
    q: str | None = None, db: Session = Depends(get_db)
) -> list[PrinterModel]:
    stmt = select(PrinterModel).order_by(PrinterModel.vendor, PrinterModel.name)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(PrinterModel.vendor.ilike(pattern), PrinterModel.name.ilike(pattern))
        )
    return list(db.scalars(stmt).all())


@router.post(
    "", response_model=PrinterModelRead, status_code=status.HTTP_201_CREATED
)
def create_printer_model(
    data: PrinterModelCreate, db: Session = Depends(get_db)
) -> PrinterModel:
    model = PrinterModel(**data.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.get("/{model_id}", response_model=PrinterModelRead)
def get_printer_model(model_id: int, db: Session = Depends(get_db)) -> PrinterModel:
    return _get_printer_model(db, model_id)


@router.patch("/{model_id}", response_model=PrinterModelRead)
def update_printer_model(
    model_id: int, data: PrinterModelUpdate, db: Session = Depends(get_db)
) -> PrinterModel:
    model = _get_printer_model(db, model_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    db.commit()
    db.refresh(model)
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_printer_model(model_id: int, db: Session = Depends(get_db)) -> Response:
    model = _get_printer_model(db, model_id)
    in_use = db.scalar(
        select(func.count(Printer.id)).where(Printer.model_id == model_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Модель используется принтерами и не может быть удалена",
        )
    db.delete(model)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
