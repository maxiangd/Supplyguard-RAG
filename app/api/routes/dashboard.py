"""风险看板 API：聚合实时风险指标，替代前端 mock 数据。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_database_session
from app.db.tables import Approval, AuditLog, User
from app.services.graph import impact, overview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> dict:
    """返回当前角色可见的看板聚合数据。"""
    role = current_user.role

    # ── 1. 统计卡片 ──
    # 待复核：审批表中 status=pending 的单子
    pending_count = db.scalar(
        select(text("count(1)"))
        .select_from(Approval)
        .where(Approval.status == "pending")
    ) or 0

    # 高风险供应商 & 活跃事件：从图谱数据拿
    try:
        graph_data = overview(role)
        nodes = graph_data["nodes"]
        high_risk_suppliers = [
            n for n in nodes
            if n["type"] == "supplier" and n.get("risk_level") == "high"
        ]
        active_events = [n for n in nodes if n["type"] == "event"]
    except Exception:
        high_risk_suppliers = []
        active_events = []

    # 越权拦截：审计日志中 action 含 blocked 的记录
    blocked_count = db.scalar(
        select(text("count(1)"))
        .select_from(AuditLog)
        .where(AuditLog.action.like("%blocked%"))
    ) or 0

    stats = [
        {
            "key": "high_risk",
            "label": "高风险供应商",
            "value": len(high_risk_suppliers),
            "color": "#f56c6c",
        },
        {
            "key": "pending_review",
            "label": "待复核结论",
            "value": pending_count,
            "color": "#e6a23c",
        },
        {
            "key": "active_events",
            "label": "活跃风险事件",
            "value": len(active_events),
            "color": "#409eff",
        },
        {
            "key": "blocked",
            "label": "本月越权拦截",
            "value": blocked_count,
            "color": "#67c23a",
        },
    ]

    # ── 2. 高风险供应商 ──
    supplier_list = []
    for s in high_risk_suppliers[:10]:
        supplier_list.append({
            "supplier_id": s["id"],
            "name": s["name"],
            "region": s.get("region", ""),
            "risk_level": s.get("risk_level", "high"),
            "score": {"high": 85, "medium": 60, "low": 30}.get(s.get("risk_level"), 60),
            "reason": s.get("desc", ""),
        })

    # ── 3. 待复核结论 ──
    approvals = db.scalars(
        select(Approval)
        .where(Approval.status == "pending")
        .order_by(Approval.created_at.desc())
        .limit(10)
    ).all()

    pending_reviews = []
    for a in approvals:
        pending_reviews.append({
            "review_id": a.approval_id,
            "question": a.question[:60],
            "requested_by": a.submitted_by,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
        })

    # ── 4. 最近风险事件 ──
    events_list = []
    for e in active_events[:10]:
        # 计算该事件影响的供应商数量
        affected_count = 0
        try:
            result = impact(None, e["id"], role)
            # 从路径中提取供应商节点
            supplier_ids: set[str] = set()
            for path in result["paths"]:
                for node in path.get("nodes", []):
                    if node.get("type") == "supplier":
                        supplier_ids.add(node["id"])
            affected_count = len(supplier_ids)
        except Exception:
            affected_count = 0

        events_list.append({
            "event_id": e["id"],
            "title": e["name"],
            "type": "DIRECT" if affected_count > 0 else "REGION",
            "level": e.get("risk_level", "medium"),
            "time": "2026-10-26",
            "affected": affected_count,
        })

    return {
        "stats": stats,
        "highRiskSuppliers": supplier_list,
        "pendingReviews": pending_reviews,
        "recentEvents": events_list,
    }