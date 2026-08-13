from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    get_usage_today,
)
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    token: str
    email: str
    name: str | None = None
    daily_limit: int
    used_today: int


@router.post("/register", response_model=AuthOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Email no válido.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Ese email ya está registrado.")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=(body.name or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.email)
    return AuthOut(
        token=token,
        email=user.email,
        name=user.name,
        daily_limit=settings.DAILY_SEARCH_LIMIT,
        used_today=0,
    )


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")

    token = create_token(user.id, user.email)
    return AuthOut(
        token=token,
        email=user.email,
        name=user.name,
        daily_limit=settings.DAILY_SEARCH_LIMIT,
        used_today=get_usage_today(db, user.id),
    )


@router.get("/me", response_model=AuthOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return AuthOut(
        token="",  # client already has token
        email=user.email,
        name=user.name,
        daily_limit=settings.DAILY_SEARCH_LIMIT,
        used_today=get_usage_today(db, user.id),
    )
