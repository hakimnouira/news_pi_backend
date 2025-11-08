# app/api/routes/auth.py
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import get_db_dep, authenticate
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.models.role import Role
from app.schemas.auth import Login, Token
from app.schemas.user import UserRegister, UserOut

router = APIRouter()

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db_dep)):
    # Friendly checks first
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=user_in.email,
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        # Set profile fields later via /users/me
        bio=None,
        avatar_url=None,
        is_active=True,
        hashed_password=get_password_hash(user_in.password),
    )

    # default role
    role = db.query(Role).filter_by(name="user").first()
    if role:
        user.roles.append(role)

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Handle rare race condition (unique constraints)
        raise HTTPException(status_code=400, detail="Email or username already registered")
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