"""数据库表模型（ORM）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def now_local() -> datetime:
    """当前本地时间（不带时区）。"""
    return datetime.now()


def new_uuid() -> str:
    """生成 UUID 字符串主键。"""
    return str(uuid.uuid4())


class User(Base):
    """登录账号与权限角色。"""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )
