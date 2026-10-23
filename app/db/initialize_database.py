"""数据库初始化：建表并写入演示账号（可重复执行）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.configuration import settings
from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.db.tables import User

SEED_USERS = [
    ("catl_admin", "admin"),
    ("catl_procurement", "procurement"),
    ("catl_logistics", "logistics"),
    ("catl_quality", "quality"),
    ("catl_finance", "finance"),
]


def _seed_user(session: Session, username: str, role: str) -> None:
    """账号不存在时创建。"""
    if session.scalar(select(User).where(User.username == username)) is None:
        session.add(
            User(
                username=username,
                password_hash=hash_password(settings.demo_password),
                role=role,
            )
        )


def init_db() -> None:
    """建表并确保演示账号存在。"""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        for username, role in SEED_USERS:
            _seed_user(session, username, role)
        session.commit()
