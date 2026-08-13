from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, UniqueConstraint
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_day"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, default=date.today)
    count = Column(Integer, default=0)
