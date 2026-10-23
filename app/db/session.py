"""数据库连接与会话管理。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)


def get_database_session() -> Generator[Session, None, None]:
    """每个请求一个数据库会话，结束后自动关闭。"""
    with SessionLocal() as session:
        yield session
