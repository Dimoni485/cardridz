from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool

    @computed_field
    @property
    def can_edit(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.EDITOR)

    @computed_field
    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: datetime | None = None
