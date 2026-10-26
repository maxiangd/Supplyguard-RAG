"""记忆管理接口：Redis 短期会话 + Postgres 长期记忆。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_database_session
from app.db.tables import User
from app.models.api_models import (
    LongTermMemoryCreateRequest,
    LongTermMemoryListResponse,
    LongTermMemoryResponse,
    LongTermMemoryUpdateRequest,
    SessionHistoryResponse,
)
from app.services.long_term import (
    delete_memory,
    get_memory,
    list_memories,
    save_memory,
    update_memory,
)
from app.services.memory import clear_session, get_session_history

router = APIRouter(prefix="/memory", tags=["memory"])


# ── 短期会话记忆 ──


@router.get("/session", response_model=SessionHistoryResponse)
def view_session(
    current_user: User = Depends(get_current_user),
) -> SessionHistoryResponse:
    """返回当前用户的对话历史（Redis 短期记忆）。"""
    history = get_session_history(current_user.username)
    return SessionHistoryResponse(turns=history, count=len(history))


@router.delete("/session")
def delete_session(
    current_user: User = Depends(get_current_user),
) -> dict:
    """清除当前用户的对话历史。"""
    ok = clear_session(current_user.username)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 不可用，无法清除会话",
        )
    return {"status": "ok"}


# ── 长期记忆 ──


@router.get("/long-term", response_model=LongTermMemoryListResponse)
def list_long_term_memories(
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> LongTermMemoryListResponse:
    """列出长期记忆。admin 全见，其他角色只看自己。"""
    items = list_memories(db, current_user, category)
    return LongTermMemoryListResponse(
        items=[
            LongTermMemoryResponse(
                memory_id=m.memory_id,
                username=m.username,
                role=m.role,
                category=m.category,
                title=m.title,
                content=m.content,
                evidence=m.evidence,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in items
        ],
        total=len(items),
    )


@router.post("/long-term", response_model=LongTermMemoryResponse)
def create_long_term_memory(
    payload: LongTermMemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> LongTermMemoryResponse:
    """保存一条长期记忆。"""
    memory = save_memory(
        db,
        username=current_user.username,
        role=current_user.role,
        category=payload.category,
        title=payload.title,
        content=payload.content,
        evidence=payload.evidence,
    )
    db.commit()
    return LongTermMemoryResponse(
        memory_id=memory.memory_id,
        username=memory.username,
        role=memory.role,
        category=memory.category,
        title=memory.title,
        content=memory.content,
        evidence=memory.evidence,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get("/long-term/{memory_id}", response_model=LongTermMemoryResponse)
def get_long_term_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> LongTermMemoryResponse:
    """查看单条长期记忆。admin 全见，其他角色只能看自己的。"""
    memory = get_memory(db, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记忆不存在")
    if current_user.role != "admin" and memory.username != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看")
    return LongTermMemoryResponse(
        memory_id=memory.memory_id,
        username=memory.username,
        role=memory.role,
        category=memory.category,
        title=memory.title,
        content=memory.content,
        evidence=memory.evidence,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.patch("/long-term/{memory_id}", response_model=LongTermMemoryResponse)
def update_long_term_memory(
    memory_id: str,
    payload: LongTermMemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> LongTermMemoryResponse:
    """更新一条长期记忆。"""
    memory = update_memory(
        db,
        memory_id,
        current_user,
        title=payload.title,
        content=payload.content,
        category=payload.category,
    )
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记忆不存在或无权修改",
        )
    db.commit()
    return LongTermMemoryResponse(
        memory_id=memory.memory_id,
        username=memory.username,
        role=memory.role,
        category=memory.category,
        title=memory.title,
        content=memory.content,
        evidence=memory.evidence,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.delete("/long-term/{memory_id}")
def delete_long_term_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> dict:
    """删除一条长期记忆。"""
    ok = delete_memory(db, memory_id, current_user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记忆不存在或无权删除",
        )
    db.commit()
    return {"status": "ok"}