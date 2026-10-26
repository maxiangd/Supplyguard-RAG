"""审批路由：审批单列表、详情与批准/驳回。"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_database_session
from app.db.tables import Approval, User
from app.models.api_models import (
    ApprovalDecisionRequest,
    ApprovalDetail,
    ApprovalListResponse,
    ApprovalSummary,
    ChunkHit,
    GraphPath,
)
from app.services.approval import (
    STATUS_PENDING,
    decide_approval,
    delete_approval,
    get_approval,
    list_approvals,
)
from app.services.workflow import submit_decision

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _summary(approval: Approval) -> ApprovalSummary:
    """把审批单 ORM 对象转成列表项。"""
    return ApprovalSummary(
        approval_id=approval.approval_id,
        question=approval.question,
        risk_level=approval.risk_level,
        reason=approval.reason,
        status=approval.status,
        submitted_by=approval.submitted_by,
        submitted_role=approval.submitted_role,
        decided_by=approval.decided_by,
        decided_at=approval.decided_at,
        decision_comment=approval.decision_comment,
        created_at=approval.created_at,
    )


@router.get("", response_model=ApprovalListResponse)
def list_approval_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> ApprovalListResponse:
    """返回审批单列表：管理员看全部，其他角色只看自己提交的。"""
    return ApprovalListResponse(
        items=[_summary(approval) for approval in list_approvals(db, current_user)]
    )


@router.get("/{approval_id}", response_model=ApprovalDetail)
def approval_detail(
    approval_id: str,
    db: Session = Depends(get_database_session),
) -> ApprovalDetail:
    """查看审批单详情，结论对所有角色可见。"""
    approval = get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="审批单不存在"
        )

    return ApprovalDetail(
        **_summary(approval).model_dump(),
        answer=approval.answer,
        answer_visible=True,
        hits=[ChunkHit(**hit) for hit in json.loads(approval.hits)],
        graph_paths=[GraphPath(**path) for path in json.loads(approval.graph_paths)],
    )


@router.post("/{approval_id}/decide", response_model=ApprovalDetail)
def decide(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> ApprovalDetail:
    """批准或驳回审批单（不能处理自己提交的单子），决定与意见写入审计。"""
    approval = decide_approval(
        db, approval_id, payload.action, payload.comment, current_user
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审批单不存在、已处理、或无权审批",
        )
    db.commit()
    submit_decision(approval_id, payload.action, payload.comment)
    return approval_detail(approval_id, db)


@router.delete("/{approval_id}")
def delete(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> dict:
    """删除已处理的审批单（pending 状态的不能删）。"""
    ok = delete_approval(db, approval_id, current_user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审批单不存在、尚未处理、或无权删除",
        )
    db.commit()
    return {"status": "ok"}