# app/api/routes/users.py
from typing import List, Optional
from pathlib import Path
import time

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Request, Body
)
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, get_current_user, require_admin

from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter()

AVATAR_DIR = Path("static/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
def update_me(
    updates: UserUpdate = Body(...),
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    # prevent username collisions
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
    # optional: allow JSON to set avatar_path directly (not typical; uploads use /avatar)
    if hasattr(updates, "avatar_path") and updates.avatar_path is not None:
        current_user.avatar_path = updates.avatar_path

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/avatar", response_model=UserOut, status_code=status.HTTP_200_OK)
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    # Save as a stable per-user filename (overwrite old), or timestamped—your call
    ext = (file.filename.rsplit(".", 1)[-1] or "jpg").lower()
    filename = f"user_{current_user.id}.{ext}"
    path = AVATAR_DIR / filename

    with path.open("wb") as f:
        f.write(file.file.read())

    # Store a simple relative path (served by /static)
    current_user.avatar_path = f"/static/avatars/{filename}"

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db_dep), _: User = Depends(get_current_user)):
    return db.query(User).all()
@router.put("/{user_id}/active", response_model=UserOut, status_code=status.HTTP_200_OK)
def set_user_active(
    user_id: int,
    payload: dict,                              # expects {"is_active": true/false}
    db: Session = Depends(get_db_dep),
    _: User = Depends(require_admin),           # admin only
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "is_active" not in payload:
        raise HTTPException(status_code=400, detail="Missing is_active")

    user.is_active = bool(payload["is_active"])
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
