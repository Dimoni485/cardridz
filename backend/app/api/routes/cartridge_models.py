from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Cartridge, CartridgeModel, PrinterModel
from app.schemas.catalog import (
    CartridgeModelCreate,
    CartridgeModelRead,
    CartridgeModelUpdate,
)

router = APIRouter(prefix="/cartridge-models", tags=["cartridge-models"])


def _get_cartridge_model(db: Session, model_id: int) -> CartridgeModel:
    model = db.get(CartridgeModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Модель картриджа не найдена")
    return model


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


@router.get("", response_model=list[CartridgeModelRead])
def list_cartridge_models(
    q: str | None = None, db: Session = Depends(get_db)
) -> list[CartridgeModel]:
    stmt = select(CartridgeModel).order_by(CartridgeModel.vendor, CartridgeModel.name)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(CartridgeModel.vendor.ilike(pattern), CartridgeModel.name.ilike(pattern))
        )
    return list(db.scalars(stmt).all())


@router.post(
    "", response_model=CartridgeModelRead, status_code=status.HTTP_201_CREATED
)
def create_cartridge_model(
    data: CartridgeModelCreate, db: Session = Depends(get_db)
) -> CartridgeModel:
    printer_models = _resolve_printer_models(db, data.printer_model_ids)
    model = CartridgeModel(**data.model_dump(exclude={"printer_model_ids"}))
    model.printer_models = printer_models
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.get("/{model_id}", response_model=CartridgeModelRead)
def get_cartridge_model(
    model_id: int, db: Session = Depends(get_db)
) -> CartridgeModel:
    return _get_cartridge_model(db, model_id)


@router.patch("/{model_id}", response_model=CartridgeModelRead)
def update_cartridge_model(
    model_id: int, data: CartridgeModelUpdate, db: Session = Depends(get_db)
) -> CartridgeModel:
    model = _get_cartridge_model(db, model_id)
    payload = data.model_dump(exclude_unset=True)
    printer_model_ids = payload.pop("printer_model_ids", None)
    for field, value in payload.items():
        setattr(model, field, value)
    if printer_model_ids is not None:
        model.printer_models = _resolve_printer_models(db, printer_model_ids)
    db.commit()
    db.refresh(model)
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cartridge_model(
    model_id: int, db: Session = Depends(get_db)
) -> Response:
    model = _get_cartridge_model(db, model_id)
    in_use = db.scalar(
        select(func.count(Cartridge.id)).where(Cartridge.model_id == model_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Модель используется картриджами и не может быть удалена",
        )
    db.delete(model)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
