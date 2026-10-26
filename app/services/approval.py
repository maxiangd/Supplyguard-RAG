"""审批服务：风险分级、审批单创建/查询/决定，审批动作同时写入审计。"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import Approval, User, now_local
from app.services.audit import record_audit

# 风险等级分值：HIGH=3 及以上需要人工审批，阈值固定便于 Benchmark 对照
SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
APPROVAL_RISK_THRESHOLD = 3

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def approval_decision(graph_paths: list[dict]) -> tuple[bool, str, str]:
    """取图谱路径中最高的风险等级，达到阈值就返回 (需要审批, 等级, 原因)。"""
    worst = max(graph_paths, key=lambda path: SEVERITY_RANK.get(path["severity"], 1))
    level = worst["severity"]
    need = SEVERITY_RANK.get(level, 1) >= APPROVAL_RISK_THRESHOLD
    reason = f"图谱影响路径最高风险等级为 {level}：{worst['summary']}"
    return need, level, reason


def create_approval(
    db: Session,
    question: str,
    answer: str,
    hits: list[dict],
    graph_paths: list[dict],
    level: str,
    reason: str,
    user: User,
) -> Approval:
    """创建待审批记录，把创建动作写入审计。"""
    approval = Approval(
        question=question,
        answer=answer,
        risk_level=level,
        reason=reason,
        submitted_by=user.username,
        submitted_role=user.role,
        status=STATUS_PENDING,
        hits=json.dumps(hits, ensure_ascii=False),
        graph_paths=json.dumps(graph_paths, ensure_ascii=False),
    )
    db.add(approval)
    db.flush()  # 先生成主键，供审计日志引用
    record_audit(
        db,
        actor=user.username,
        actor_role=user.role,
        action="approval.created",
        target_type="approval",
        target_id=approval.approval_id,
        detail={"question": question, "risk_level": level, "reason": reason},
    )
    return approval


def list_approvals(db: Session, user: User) -> list[Approval]:
    """管理员看全部审批单，其他角色只看自己提交的。"""
    statement = select(Approval).order_by(Approval.created_at.desc())
    if user.role != "admin":
        statement = statement.where(Approval.submitted_by == user.username)
    return list(db.scalars(statement))


def get_approval(db: Session, approval_id: str) -> Approval | None:
    """按单号取审批单，不做权限过滤。"""
    return db.get(Approval, approval_id)


def decide_approval(
    db: Session,
    approval_id: str,
    action: str,
    comment: str | None,
    decider: User,
) -> Approval | None:
    """决定审批单。管理员可审全部，其他角色只能审自己提交的。"""
    approval = db.get(Approval, approval_id)
    if approval is None or approval.status != STATUS_PENDING:
        return None
    if decider.role != "admin" and approval.submitted_by != decider.username:
        return None
    approval.status = STATUS_APPROVED if action == "approve" else STATUS_REJECTED
    approval.decision_comment = comment or None
    approval.decided_by = decider.username
    approval.decided_at = now_local()
    record_audit(
        db,
        actor=decider.username,
        actor_role=decider.role,
        action=f"approval.{action}",
        target_type="approval",
        target_id=approval_id,
        detail={"comment": comment or ""},
    )
    return approval


def delete_approval(
    db: Session,
    approval_id: str,
    user: User,
) -> bool:
    """删除审批单。已处理的（approved/rejected）才能删，未处理的不能删。
    管理员可删全部已处理单，其他角色只能删自己提交的已处理单。"""
    approval = db.get(Approval, approval_id)
    if approval is None:
        return False
    # 未处理的不能删
    if approval.status == STATUS_PENDING:
        return False
    # 只有 admin 或提交人自己能删
    if user.role != "admin" and approval.submitted_by != user.username:
        return False

    record_audit(
        db,
        actor=user.username,
        actor_role=user.role,
        action="approval.deleted",
        target_type="approval",
        target_id=approval_id,
        detail={"status": approval.status},
    )
    db.delete(approval)
    db.flush()
    return True