"""数据库表模型（ORM）。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

DOCUMENT_STATUS_QUEUED = "queued"
DOCUMENT_STATUS_PROCESSING = "processing"
DOCUMENT_STATUS_READY = "ready"
DOCUMENT_STATUS_FAILED = "failed"


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
    # 禁用账号保留记录，但不能再登录或访问接口
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )


class Document(Base):
    """上传的原始文档及其摄取状态。"""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 可检索到该文档的角色；admin 不走这里，始终可见
    allowed_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False
    )
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DOCUMENT_STATUS_QUEUED
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime)
