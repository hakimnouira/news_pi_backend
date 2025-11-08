from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, get_current_user
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter()

@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserOut)
def update_me(
    updates: UserUpdate,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    # prevent username/email collisions
    if updates.username and updates.username != current_user.username:
        exists = db.query(User).filter(User.username == updates.username).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    # apply updates if provided
    if updates.username is not None:
        current_user.username = updates.username
    if updates.first_name is not None:
        current_user.first_name = updates.first_name
    if updates.last_name is not None:
        current_user.last_name = updates.last_name
    if updates.bio is not None:
        current_user.bio = updates.bio
    if updates.avatar_url is not None:
        current_user.avatar_url = str(updates.avatar_url)
    # optional: allow user to toggle is_active — usually NO for self, so you can ignore or restrict

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db_dep), _: User = Depends(get_current_user)):
    return db.query(User).all()
