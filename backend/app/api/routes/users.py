from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.common import Message
from app.schemas.user import (
    UserAdminRead,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


def _active_admins(db: Session, exclude_id: int | None = None) -> int:
    stmt = select(func.count(User.id)).where(
        User.role == UserRole.ADMIN.value, User.is_active.is_(True)
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return db.scalar(stmt) or 0


@router.get("", response_model=list[UserAdminRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserAdminRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(
        username=data.username.strip(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=data.role.value,
        is_active=data.is_active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Пользователь с таким логином уже существует"
        ) from exc
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserAdminRead)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    user = _get_user(db, user_id)
    payload = data.model_dump(exclude_unset=True)

    if user.id == current_user.id:
        if payload.get("role") not in (None, UserRole.ADMIN):
            raise HTTPException(
                status_code=400,
                detail="Нельзя понизить собственную учётную запись",
            )
        if payload.get("is_active") is False:
            raise HTTPException(
                status_code=400, detail="Нельзя деактивировать собственную учётную запись"
            )

    new_role = payload.get("role")
    new_active = payload.get("is_active")
    loses_admin = (
        user.role == UserRole.ADMIN.value
        and (
            (new_role is not None and new_role != UserRole.ADMIN)
            or new_active is False
        )
    )
    if loses_admin and _active_admins(db, exclude_id=user.id) == 0:
        raise HTTPException(
            status_code=400,
            detail="В системе должен остаться хотя бы один активный администратор",
        )

    if "full_name" in payload and payload["full_name"] is not None:
        user.full_name = payload["full_name"].strip()
    if new_role is not None:
        user.role = new_role.value
    if new_active is not None:
        user.is_active = new_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/password", response_model=Message)
def reset_password(
    user_id: int,
    data: UserPasswordReset,
    db: Session = Depends(get_db),
) -> Message:
    user = _get_user(db, user_id)
    user.password_hash = hash_password(data.password)
    db.commit()
    return Message(detail="Пароль обновлён")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    user = _get_user(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Нельзя удалить собственную учётную запись"
        )
    if user.role == UserRole.ADMIN.value and user.is_active:
        if _active_admins(db, exclude_id=user.id) == 0:
            raise HTTPException(
                status_code=400,
                detail="В системе должен остаться хотя бы один активный администратор",
            )
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
