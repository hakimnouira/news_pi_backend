from pydantic import BaseModel, EmailStr, Field, AnyUrl
from typing import List, Optional

class RoleBase(BaseModel):
    name: str

class RoleOut(RoleBase):
    id: int
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=2000)
    avatar_url: Optional[AnyUrl] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    # all optional for partial update
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=2000)
    avatar_url: Optional[AnyUrl] = None
    is_active: Optional[bool] = None  # keep if admins may toggle via a different endpoint

class UserOut(UserBase):
    id: int
    roles: List[RoleOut] = []
    class Config:
        from_attributes = True
