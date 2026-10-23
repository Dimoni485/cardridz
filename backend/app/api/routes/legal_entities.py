from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Department, LegalEntity
from app.schemas.legal_entity import (
    LegalEntityCreate,
    LegalEntityRead,
    LegalEntityUpdate,
)

router = APIRouter(prefix="/legal-entities", tags=["legal-entities"])


def _get_entity(db: Session, entity_id: int) -> LegalEntity:
    entity = db.scalar(
        select(LegalEntity)
        .options(selectinload(LegalEntity.departments))
        .where(LegalEntity.id == entity_id)
    )
    if entity is None:
        raise HTTPException(status_code=404, detail="Юрлицо не найдено")
    return entity


@router.get("", response_model=list[LegalEntityRead])
def list_legal_entities(
    q: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[LegalEntity]:
    stmt = (
        select(LegalEntity)
        .options(selectinload(LegalEntity.departments))
        .order_by(LegalEntity.name)
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(LegalEntity.name.ilike(pattern), LegalEntity.inn.ilike(pattern))
        )
    if active_only:
        stmt = stmt.where(LegalEntity.is_active.is_(True))
    return list(db.scalars(stmt).unique().all())


@router.post(
    "", response_model=LegalEntityRead, status_code=status.HTTP_201_CREATED
)
def create_legal_entity(
    data: LegalEntityCreate, db: Session = Depends(get_db)
) -> LegalEntity:
    entity = LegalEntity(**data.model_dump())
    db.add(entity)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Юрлицо с таким наименованием уже существует"
        ) from exc
    return _get_entity(db, entity.id)


@router.get("/{entity_id}", response_model=LegalEntityRead)
def get_legal_entity(entity_id: int, db: Session = Depends(get_db)) -> LegalEntity:
    return _get_entity(db, entity_id)


@router.patch("/{entity_id}", response_model=LegalEntityRead)
def update_legal_entity(
    entity_id: int, data: LegalEntityUpdate, db: Session = Depends(get_db)
) -> LegalEntity:
    entity = _get_entity(db, entity_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Юрлицо с таким наименованием уже существует"
        ) from exc
    db.expire(entity)
    return _get_entity(db, entity_id)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_legal_entity(entity_id: int, db: Session = Depends(get_db)) -> Response:
    entity = _get_entity(db, entity_id)
    departments = db.scalar(
        select(func.count(Department.id)).where(
            Department.legal_entity_id == entity_id
        )
    )
    if departments:
        raise HTTPException(
            status_code=409,
            detail="У юрлица есть отделы. Сначала удалите или перенесите отделы.",
        )
    db.delete(entity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
