from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: UserRole | None = None
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserAdminRead(BaseModel):
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
