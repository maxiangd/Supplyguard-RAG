"""长期记忆 CRUD：PostgreSQL 持久化的用户偏好、洞察与笔记。

与 app/services/memory.py（Redis 短期会话）互补：
- 短期记忆自动追加/过期，用于多轮对话上下文
- 长期记忆由用户或系统显式保存，用于跨会话的知识积累
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tables import LongTermMemory, User


def save_memory(
    db: Session,
    username: str,
    role: str,
    category: str,
    title: str,
    content: str,
    evidence: str | None = None,
) -> LongTermMemory:
    """创建一条长期记忆记录。"""
    memory = LongTermMemory(
        username=username,
        role=role,
        category=category,
        title=title,
        content=content,
        evidence=evidence,
    )
    db.add(memory)
    db.flush()
    return memory


def list_memories(
    db: Session,
    user: User,
    category: str | None = None,
    limit: int = 50,
) -> list[LongTermMemory]:
    """按角色查看长期记忆：admin 全见，其他角色只看自己的。"""
    statement = select(LongTermMemory).order_by(LongTermMemory.updated_at.desc())

    if user.role != "admin":
        statement = statement.where(LongTermMemory.username == user.username)

    if category:
        statement = statement.where(LongTermMemory.category == category)

    statement = statement.limit(limit)
    return list(db.scalars(statement))


def get_memory(db: Session, memory_id: str) -> LongTermMemory | None:
    """按 ID 取单条记忆。"""
    return db.get(LongTermMemory, memory_id)


def update_memory(
    db: Session,
    memory_id: str,
    user: User,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
) -> LongTermMemory | None:
    """更新一条长期记忆。admin 可改任意，其他角色只能改自己的。"""
    memory = db.get(LongTermMemory, memory_id)
    if memory is None:
        return None
    if user.role != "admin" and memory.username != user.username:
        return None

    if title is not None:
        memory.title = title
    if content is not None:
        memory.content = content
    if category is not None:
        memory.category = category

    db.flush()
    return memory


def delete_memory(db: Session, memory_id: str, user: User) -> bool:
    """删除一条长期记忆。admin 可删任意，其他角色只能删自己的。"""
    memory = db.get(LongTermMemory, memory_id)
    if memory is None:
        return False
    if user.role != "admin" and memory.username != user.username:
        return False

    db.delete(memory)
    db.flush()
    return True