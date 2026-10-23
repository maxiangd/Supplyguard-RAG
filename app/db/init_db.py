"""数据库初始化：建表并写入演示账号（可重复执行）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User
from app.db.session import Base, SessionLocal, engine

# 每个角色一个演示账号，共用一个演示密码
SEED_USERS = [
    ("catl_admin", "admin"),
    ("catl_procurement", "procurement"),
    ("catl_logistics", "logistics"),
    ("catl_quality", "quality"),
    ("catl_finance", "finance"),
]


def _seed_user(session: Session, username: str, role: str) -> None:
    """确保演示账号存在。

    参数：
        session —— 由调用方创建的数据库会话。
        username —— 账号名。
        role —— 该账号的角色。
    返回：None。已存在账号时保留原密码与角色，不覆盖。
    """
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        session.add(
            User(
                username=username,
                password_hash=hash_password(settings.demo_password),
                role=role,
            )
        )


def init_db() -> None:
    """初始化数据库：建表并写入演示账号。

    由应用启动时调用；重复执行不会产生重复数据，也不会覆盖已有密码。
    参数：无。
    返回：None。失败时抛出异常，由调用方决定是否终止启动。
    """
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        for username, role in SEED_USERS:
            _seed_user(session, username, role)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()