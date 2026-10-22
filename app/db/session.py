"""数据库连接与会话管理。

本文件只负责三件事：
    1. 创建 Engine（连接池）
    2. 提供 Session 工厂（每次操作数据库时创建会话）
    3. 提供 FastAPI 依赖 get_db（每个请求自动开关会话）

表结构（模型类）不在这里，放在 db/models.py。
"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的共同父类。

    继承它之后，SQLAlchemy 才能知道「哪些类对应数据库表」。
    后面的 Tenant、User 等模型都写成 class Xxx(Base)，
    表名和字段由模型类里的 mapped_column 声明。
    """


def _build_engine(database_url: str) -> Engine:
    """根据连接串创建 Engine，并处理 SQLite 的特殊配置。

    参数：
        database_url：例如 "sqlite:///./data/app.db" 或
                      "postgresql+psycopg://user:pass@host/db"。
    返回：
        配置好的 Engine 对象（内部维护连接池）。
    """
    # pool_pre_ping：每次从连接池取连接前先发一个轻量探测。
    # 数据库可能因为空闲超时、网络中断已经断开了连接，
    # 没有这个选项时，请求会拿到一条"看起来正常其实已死"的连接然后报错；
    # 打开后 SQLAlchemy 会自动丢弃坏连接并换新的。
    kwargs: dict = {"pool_pre_ping": True}

    if database_url.startswith("sqlite"):
        # SQLite 默认禁止跨线程使用同一个连接。
        # FastAPI 会把同步路由函数丢进线程池执行，
        # 所以必须关掉这个检查，否则会报 "SQLite objects created in a thread..."。
        kwargs["connect_args"] = {"check_same_thread": False}

        # SQLite 的数据库就是一个文件。文件所在目录不存在时，
        # 连接会直接失败，所以先把目录建出来（例如 ./data）。
        path = database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    # 其他数据库（Postgres）用默认连接池参数即可：
    # 默认最多 5 个常驻连接 + 10 个临时溢出连接，对本项目够用。
    eng = create_engine(database_url, **kwargs)

    if database_url.startswith("sqlite"):
        # SQLite 默认不检查外键！表里声明的 ForeignKey 和 CASCADE
        # 在 SQLite 上会静默失效（写进不存在的 tenant_id 也不报错）。
        # 必须每建立一条连接就执行一次 PRAGMA 打开检查。
        # 用 event 监听 "connect"，可以保证连接池里每条新连接都设置过。
        @event.listens_for(eng, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            """SQLite 连接建立时启用外键约束检查。"""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return eng


# 模块导入时创建一次，全应用共享同一个连接池。
# 注意：这里的配置来自 .env 的 APP_DATABASE_URL。
engine = _build_engine(settings.database_url)

# sessionmaker 是"生产 Session 的工厂"，不是 Session 本身。
# 调用 SessionLocal() 才会得到一个新的会话。
SessionLocal = sessionmaker(
    bind=engine,              # 指明这个会话用哪个 Engine
    autocommit=False,         # 事务由业务代码明确 commit，出错时可以整体回滚
    autoflush=False,          # 查询前不自动把内存改动刷进数据库，行为更可预测
    expire_on_commit=False,   # commit 之后对象属性仍可读取；否则会话关闭后再访问会报错
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求拿一个 Session，请求结束自动关闭。

    用法（后面的路由会这样写）：
        def endpoint(db: Session = Depends(get_db)):
            ...

    yield 之前是"请求开始"要做的事，yield 之后是"请求结束"的清理。
    FastAPI 会在响应返回后继续执行 finally，所以连接一定会被归还。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # 只 close 不 commit：没提交的改动会被丢弃，避免半截事务写进数据库。
        db.close()
