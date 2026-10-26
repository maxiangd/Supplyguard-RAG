"""审计服务：只追加写入审计日志，并提供查询。"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import AuditLog


def record_audit(
    db: Session,
    actor: str,
    actor_role: str,
    action: str,
    target_type: str | None,
    target_id: str | None,
    detail: dict,
) -> None:
    """追加一条审计记录，detail 以 JSON 字符串存储。"""
    db.add(
        AuditLog(
            actor=actor,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail, ensure_ascii=False),
        )
    )
    # 立即落地，保证同一事务内立即可查到（会话默认 autoflush=False）
    db.flush()


def list_audit_logs(db: Session, limit: int) -> list[AuditLog]:
    """按时间倒序返回最近的审计记录。"""
    statement = (
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    return list(db.scalars(statement))