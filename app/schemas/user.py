# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import List, Optional
import re

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9._-]{3,50}$")
RESERVED_USERNAMES = {"admin", "root", "system", "support"}

# Password: ≥8 chars, at least one lowercase, uppercase, digit, special
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&/#^+=._-])[A-Za-z\d@$!%*?&/#^+=._-]{8,}$"
)


# ---------- Roles ----------
class RoleBase(BaseModel):
    name: str


class RoleOut(RoleBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Registration-only input ----------
class UserRegister(BaseModel):
    # Only the fields allowed at signup
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    first_name: str | None = None
    last_name: str | None = None
    password: str = Field(..., min_length=8)

    # Forbid extra fields like bio, avatar_path, is_active during registration
    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> EmailStr:
        return str(v).strip().lower()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_REGEX.match(v):
            raise ValueError("Username must be 3–50 chars; allowed: letters, numbers, dot, underscore, hyphen.")
        if v.lower() in RESERVED_USERNAMES:
            raise ValueError("This username is reserved. Please choose another.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not PASSWORD_REGEX.match(v):
            raise ValueError(
                "Password must be at least 8 characters and include: uppercase, lowercase, number, and special character."
            )
        return v


# ---------- Full user shapes for responses & profile update ----------
class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=2000)
    # Store only a relative file path like "/static/avatars/user_12.png"
    avatar_path: Optional[str] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=2000)
    # Accept a relative path if you ever set it via JSON (uploads usually handled by a separate endpoint)
    avatar_path: Optional[str] = None
    is_active: Optional[bool] = None  # typically admin-only


class UserOut(UserBase):
    id: int
    roles: List[RoleOut] = []

    class Config:
        from_attributes = True
