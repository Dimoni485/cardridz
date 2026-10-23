from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Cartridge, Operation, ServiceProvider
from app.schemas.service_provider import (
    ServiceProviderCreate,
    ServiceProviderRead,
    ServiceProviderUpdate,
)

router = APIRouter(prefix="/service-providers", tags=["service-providers"])


def _get_provider(db: Session, provider_id: int) -> ServiceProvider:
    provider = db.get(ServiceProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Сервисная организация не найдена")
    return provider


@router.get("", response_model=list[ServiceProviderRead])
def list_service_providers(
    q: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[ServiceProvider]:
    stmt = select(ServiceProvider).order_by(ServiceProvider.name)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ServiceProvider.name.ilike(pattern),
                ServiceProvider.inn.ilike(pattern),
                ServiceProvider.contact_person.ilike(pattern),
            )
        )
    if active_only:
        stmt = stmt.where(ServiceProvider.is_active.is_(True))
    return list(db.scalars(stmt).all())


@router.post(
    "", response_model=ServiceProviderRead, status_code=status.HTTP_201_CREATED
)
def create_service_provider(
    data: ServiceProviderCreate, db: Session = Depends(get_db)
) -> ServiceProvider:
    provider = ServiceProvider(**data.model_dump())
    db.add(provider)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Организация с таким наименованием уже существует",
        ) from exc
    db.refresh(provider)
    return provider


@router.get("/{provider_id}", response_model=ServiceProviderRead)
def get_service_provider(
    provider_id: int, db: Session = Depends(get_db)
) -> ServiceProvider:
    return _get_provider(db, provider_id)


@router.patch("/{provider_id}", response_model=ServiceProviderRead)
def update_service_provider(
    provider_id: int, data: ServiceProviderUpdate, db: Session = Depends(get_db)
) -> ServiceProvider:
    provider = _get_provider(db, provider_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Организация с таким наименованием уже существует",
        ) from exc
    db.refresh(provider)
    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_provider(
    provider_id: int, db: Session = Depends(get_db)
) -> Response:
    provider = _get_provider(db, provider_id)
    in_use = (
        db.scalar(
            select(func.count(Operation.id)).where(
                Operation.service_provider_id == provider_id
            )
        )
        or db.scalar(
            select(func.count(Cartridge.id)).where(
                Cartridge.service_provider_id == provider_id
            )
        )
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=(
                "Организация используется в операциях. "
                "Деактивируйте её вместо удаления."
            ),
        )
    db.delete(provider)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
