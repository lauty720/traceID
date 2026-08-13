from datetime import datetime, timedelta, date
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UsageLog

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada. Volvé a iniciar sesión.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido. Volvé a iniciar sesión.")


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Tenés que iniciar sesión para analizar imágenes.")
    data = decode_token(creds.credentials)
    user = db.query(User).filter(User.id == int(data["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return user


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not creds or not creds.credentials:
        return None
    try:
        data = decode_token(creds.credentials)
        return db.query(User).filter(User.id == int(data["sub"])).first()
    except Exception:
        return None


def get_usage_today(db: Session, user_id: int) -> int:
    today = date.today()
    row = db.query(UsageLog).filter(UsageLog.user_id == user_id, UsageLog.day == today).first()
    return row.count if row else 0


def increment_usage(db: Session, user_id: int) -> int:
    today = date.today()
    row = db.query(UsageLog).filter(UsageLog.user_id == user_id, UsageLog.day == today).first()
    if not row:
        row = UsageLog(user_id=user_id, day=today, count=1)
        db.add(row)
    else:
        row.count += 1
    db.commit()
    return row.count


def check_daily_limit(db: Session, user: User) -> None:
    used = get_usage_today(db, user.id)
    if used >= settings.DAILY_SEARCH_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Llegaste al límite de {settings.DAILY_SEARCH_LIMIT} análisis por día. "
                "Volvé a intentar mañana."
            ),
        )
