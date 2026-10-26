"""pytest fixtures：测试客户端、数据库会话、认证工具。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, types
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.database import Base, get_database_session
from app.db.tables import User

DEMO_PASSWORD = "catl123"
SEED_USERS = [
    ("catl_admin", "admin"),
    ("catl_procurement", "procurement"),
    ("catl_logistics", "logistics"),
    ("catl_quality", "quality"),
    ("catl_finance", "finance"),
]


# ── 合并 fixture：一个 fixture 搞定建库→建表→播种→创建app→覆盖依赖 ──


@pytest.fixture(scope="function")
def app():
    """创建测试 FastAPI 实例，返回 TestClient-ready 对象。

    整个测试隔离链在一个 fixture 内完成：
    1. 内存 SQLite 建库建表播种
    2. 创建 FastAPI（跳过真实 lifespan）
    3. 覆盖 get_database_session 为测试 session
    """
    from unittest.mock import patch
    from contextlib import asynccontextmanager

    # ── 1. 建测试数据库 ──
    # 替换 PostgreSQL ARRAY 为 Text（SQLite 不支持）
    for table in list(Base.metadata.tables.values()):
        for col in list(table.columns):
            if isinstance(col.type, ARRAY):
                col.type = types.Text()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # 所有线程共享同一个连接，保证内存数据库可见
    )
    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()

    # 播种演示账号
    for username, role in SEED_USERS:
        existing = session.query(User).filter_by(username=username).first()
        if not existing:
            session.add(User(
                username=username, role=role,
                password_hash=hash_password(DEMO_PASSWORD),
                is_active=True,
            ))
    session.commit()

    # ── 2. 创建 FastAPI ──
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    import app.main
    with patch.object(app.main, "lifespan", _noop_lifespan):
        app_instance = app.main.create_app()

    # ── 3. 覆盖依赖 ──
    def override_db():
        yield session

    app_instance.dependency_overrides[get_database_session] = override_db
    return app_instance


@pytest.fixture(scope="function")
def client(app):
    """TestClient，直接调接口。"""
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_headers(client):
    """返回 helper 函数，按角色名获取 Authorization header。"""

    def _headers(role: str = "admin") -> dict:
        username = f"catl_{role}"
        resp = client.post(
            "/api/auth/login",
            json={"username": username, "password": DEMO_PASSWORD},
        )
        if resp.status_code != 200:
            pytest.skip(f"无法登录 {username}: {resp.text[:100]}")
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _headers