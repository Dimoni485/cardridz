from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Department, Employee, LegalEntity
from app.schemas.legal_entity import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
)

router = APIRouter(prefix="/departments", tags=["departments"])


def _get_department(db: Session, department_id: int) -> Department:
    department = db.scalar(
        select(Department)
        .options(selectinload(Department.legal_entity))
        .where(Department.id == department_id)
    )
    if department is None:
        raise HTTPException(status_code=404, detail="Отдел не найден")
    return department


def _get_entity(db: Session, entity_id: int) -> LegalEntity:
    entity = db.get(LegalEntity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Юрлицо не найдено")
    return entity


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    legal_entity_id: int | None = None,
    q: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[Department]:
    stmt = (
        select(Department)
        .options(selectinload(Department.legal_entity))
        .join(Department.legal_entity)
        .order_by(LegalEntity.name, Department.name)
    )
    if legal_entity_id is not None:
        stmt = stmt.where(Department.legal_entity_id == legal_entity_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Department.name.ilike(pattern), Department.room.ilike(pattern))
        )
    if active_only:
        stmt = stmt.where(Department.is_active.is_(True))
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate, db: Session = Depends(get_db)
) -> Department:
    _get_entity(db, data.legal_entity_id)
    department = Department(**data.model_dump())
    db.add(department)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Отдел с таким названием уже есть у этого юрлица",
        ) from exc
    return _get_department(db, department.id)


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: int, db: Session = Depends(get_db)
) -> Department:
    return _get_department(db, department_id)


@router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: int, data: DepartmentUpdate, db: Session = Depends(get_db)
) -> Department:
    department = _get_department(db, department_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("legal_entity_id") is not None:
        _get_entity(db, payload["legal_entity_id"])
    for field, value in payload.items():
        setattr(department, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Отдел с таким названием уже есть у этого юрлица",
        ) from exc
    db.expire(department)
    return _get_department(db, department_id)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int, db: Session = Depends(get_db)
) -> Response:
    department = _get_department(db, department_id)
    employees = db.scalar(
        select(func.count(Employee.id)).where(Employee.department_id == department_id)
    )
    if employees:
        raise HTTPException(
            status_code=409,
            detail="В отделе есть сотрудники. Сначала переведите или удалите их.",
        )
    db.delete(department)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
