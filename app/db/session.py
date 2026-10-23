"""数据库连接与会话管理。"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的父类。"""


_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # SQLite 以文件形式存储，先确保目录存在
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
        parents=True, exist_ok=True
    )

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # SQLite 默认禁止跨线程使用连接，而 FastAPI 会把同步路由放进线程池
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    # SQLite 默认不检查外键，需要每条连接单独开启
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个会话，请求结束后自动关闭。

    会话不自动提交，写操作需要在路由里显式 commit。
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
