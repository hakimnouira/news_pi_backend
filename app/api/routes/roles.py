from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, require_admin, get_current_user
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleOut

router = APIRouter()

@router.get("/", response_model=List[RoleOut])
def list_roles(db: Session = Depends(get_db_dep), _: User = Depends(get_current_user)):
    return db.query(Role).order_by(Role.id.asc()).all()

@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(role_in: RoleCreate, db: Session = Depends(get_db_dep), _: User = Depends(require_admin)):
    existing = db.query(Role).filter_by(name=role_in.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = Role(name=role_in.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: Session = Depends(get_db_dep), _: User = Depends(require_admin)):
    role = db.query(Role).get(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    db.delete(role)
    db.commit()
    return

@router.post("/assign/{user_id}/{role_name}", status_code=status.HTTP_204_NO_CONTENT)
def assign_role(
    user_id: int,
    role_name: str,
    db: Session = Depends(get_db_dep),
    _: User = Depends(require_admin),
):
    from app.models.user import User as UserModel
    user = db.query(UserModel).get(user_id)
    role = db.query(Role).filter_by(name=role_name).first()
    if not user or not role:
        raise HTTPException(status_code=404, detail="User or role not found")
    if role not in user.roles:
        user.roles.append(role)
        db.add(user)
        db.commit()
    return
