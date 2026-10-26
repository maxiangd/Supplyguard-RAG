"""数据库表模型（ORM）。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
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


class Approval(Base):
    """风险审批单：高风险结论先进审批台，批准前不对提交人展示。"""

    __tablename__ = "approvals"

    approval_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # 待审批的结论草稿，批准后才解锁给提交人
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    decision_comment: Mapped[str | None] = mapped_column(String(500))
    decided_by: Mapped[str | None] = mapped_column(String(128))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    # 证据用 JSON 字符串整块保存，与向量检索/图谱接口的返回结构一致
    hits: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    graph_paths: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )


class AuditLog(Base):
    """审计日志：只追加写入，记录谁在什么时间对什么对象做了什么。"""

    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )


class LongTermMemory(Base):
    """长期记忆：用户偏好、重要洞察、反馈笔记，跨会话持久化。

    与 Redis 短期会话不同：
    - 短期记忆自动追加/过期，用于多轮对话上下文
    - 长期记忆由用户或系统显式保存，用于跨会话的知识积累
    """

    __tablename__ = "long_term_memories"

    memory_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    username: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    # 记录时的角色（方便按角色过滤记忆）
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # 记忆分类：preference（偏好）、insight（洞察）、feedback（反馈）、note（笔记）
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="note")
    # 记忆的简短标题，方便列表展示
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 正文内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 关联的证据（JSON 字符串，可选存 hits / graph_paths）
    evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_local, onupdate=now_local, nullable=False
    )
