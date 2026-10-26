"""审计路由：审计日志查询（仅管理员）。"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_database_session
from app.db.tables import User
from app.models.api_models import AuditLogResponse
from app.services.audit import list_audit_logs

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_logs(
    limit: int = 100,
    admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_database_session),
) -> list[AuditLogResponse]:
    """按时间倒序返回最近的审计记录。"""
    return [
        AuditLogResponse(
            audit_id=log.audit_id,
            actor=log.actor,
            actor_role=log.actor_role,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            detail=json.loads(log.detail) if log.detail else None,
            created_at=log.created_at,
        )
        for log in list_audit_logs(db, limit)
    ]