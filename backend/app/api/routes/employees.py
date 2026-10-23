from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Cartridge, Department, Employee, LegalEntity, Operation, Printer
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.services.loaders import EMPLOYEE_LOADS

router = APIRouter(prefix="/employees", tags=["employees"])


def _get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.scalar(
        select(Employee).options(*EMPLOYEE_LOADS).where(Employee.id == employee_id)
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


def _validate_department(db: Session, department_id: int | None) -> None:
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status_code=404, detail="Отдел не найден")


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    q: str | None = None,
    active_only: bool = False,
    department_id: int | None = None,
    legal_entity_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[Employee]:
    stmt = select(Employee).options(*EMPLOYEE_LOADS)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = (
            stmt.outerjoin(Employee.department)
            .outerjoin(Department.legal_entity)
            .where(
                or_(
                    Employee.full_name.ilike(pattern),
                    Employee.position.ilike(pattern),
                    Department.name.ilike(pattern),
                    LegalEntity.name.ilike(pattern),
                )
            )
        )
    if department_id is not None:
        stmt = stmt.where(Employee.department_id == department_id)
    if legal_entity_id is not None:
        stmt = stmt.where(Department.legal_entity_id == legal_entity_id)
    if active_only:
        stmt = stmt.where(Employee.is_active.is_(True))
    stmt = stmt.order_by(Employee.full_name)
    return list(db.scalars(stmt).unique().all())


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)) -> Employee:
    _validate_department(db, data.department_id)
    employee = Employee(**data.model_dump())
    db.add(employee)
    db.commit()
    return _get_employee(db, employee.id)


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(employee_id: int, db: Session = Depends(get_db)) -> Employee:
    return _get_employee(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)
) -> Employee:
    employee = _get_employee(db, employee_id)
    payload = data.model_dump(exclude_unset=True)
    if "department_id" in payload:
        _validate_department(db, payload["department_id"])
    for field, value in payload.items():
        setattr(employee, field, value)
    db.commit()
    db.expire(employee)
    return _get_employee(db, employee_id)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db)) -> Response:
    employee = _get_employee(db, employee_id)
    in_use = (
        db.scalar(
            select(Cartridge.id).where(Cartridge.employee_id == employee_id).limit(1)
        )
        or db.scalar(select(Printer.id).where(Printer.employee_id == employee_id).limit(1))
        or db.scalar(
            select(Operation.id).where(Operation.employee_id == employee_id).limit(1)
        )
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Сотрудник используется в учёте. Деактивируйте его вместо удаления.",
        )
    db.delete(employee)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
