from pydantic import BaseModel, EmailStr
from typing import List


class RoleBase(BaseModel):
    name: str


class RoleOut(RoleBase):
    id: int

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    roles: List[RoleOut] = []

    class Config:
        from_attributes = True
