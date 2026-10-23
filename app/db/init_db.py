"""数据库初始化：建表并写入默认租户与演示账号（可重复执行）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Tenant, User, UserTenant
from app.db.session import Base, SessionLocal, engine

DEFAULT_TENANT_ID = "catl"
DEFAULT_TENANT_NAME = "宁德时代供应链"

# 每个角色一个演示账号，共用一个演示密码
SEED_USERS = [
    ("catl_admin", "admin"),
    ("catl_procurement", "procurement"),
    ("catl_logistics", "logistics"),
    ("catl_quality", "quality"),
    ("catl_finance", "finance"),
]


def _seed_tenant(session: Session) -> Tenant:
    """确保默认租户存在；已存在则原样返回。

    参数：session —— 由调用方创建的数据库会话。
    返回：Tenant 对象（新建的或已存在的）。
    """
    tenant = session.get(Tenant, DEFAULT_TENANT_ID)
    if tenant is None:
        tenant = Tenant(tenant_id=DEFAULT_TENANT_ID, name=DEFAULT_TENANT_NAME)
        session.add(tenant)
        session.flush()

    return tenant


def _seed_user(session: Session, username: str, role: str) -> None:
    """确保演示账号存在，并加入默认租户。

    参数：
        session —— 由调用方创建的数据库会话。
        username —— 账号名。
        role —— 该账号的角色。
    返回：None。已存在账号时保留原密码与角色，不覆盖。
    """
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(settings.demo_password),
            role=role,
            default_tenant_id=DEFAULT_TENANT_ID,
        )
        session.add(user)
        session.flush()

    member = session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.user_id,
            UserTenant.tenant_id == DEFAULT_TENANT_ID,
        )
    )
    if member is None:
        session.add(UserTenant(user_id=user.user_id, tenant_id=DEFAULT_TENANT_ID))


def init_db() -> None:
    """初始化数据库：建表并写入默认租户与演示账号。

    由应用启动时调用；重复执行不会产生重复数据，也不会覆盖已有密码。
    参数：无。
    返回：None。失败时抛出异常，由调用方决定是否终止启动。
    """
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        _seed_tenant(session)
        for username, role in SEED_USERS:
            _seed_user(session, username, role)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()