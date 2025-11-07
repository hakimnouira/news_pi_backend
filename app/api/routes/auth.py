# app/api/routes/auth.py
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, authenticate
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.models.role import Role
from app.schemas.auth import Login, Token
from app.schemas.user import UserCreate, UserOut

router = APIRouter()

@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db_dep)):
    email_exists = db.query(User).filter(User.email == user_in.email).first()
    if email_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    username_exists = db.query(User).filter(User.username == user_in.username).first()
    if username_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    user = User(
        email=user_in.email,
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        bio=user_in.bio,
        avatar_url=str(user_in.avatar_url) if user_in.avatar_url else None,
        hashed_password=get_password_hash(user_in.password),
        is_active=user_in.is_active,
    )

    # assign default "user" role if exists
    role = db.query(Role).filter_by(name="user").first()
    if role:
        user.roles.append(role)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# JSON login (good for frontend / Postman)
@router.post("/login", response_model=Token)
def login(form: Login, db: Session = Depends(get_db_dep)):
    user = authenticate(db, email=form.email, password=form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    token = create_access_token(subject=user.email)
    return Token(access_token=token)

# FORM login for Swagger OAuth2 popup
@router.post("/token", response_model=Token)
def login_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db_dep)):
    # Swagger sends "username" in the form; we treat it as email
    user = authenticate(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    token = create_access_token(subject=user.email)
    return Token(access_token=token)
