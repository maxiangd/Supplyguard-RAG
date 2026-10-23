"""数据库表模型（ORM）。

ORM 的意思是：用 Python 类描述数据库表，
    类  = 一张表
    属性 = 一列
    实例 = 一行数据

当前只有 users 一张表，后续再按批次加入文档、审计等业务表。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow_naive() -> datetime:
    """返回当前 UTC 时间的 naive datetime（不带时区信息）。

    为什么不用数据库的 NOW()？
        各数据库函数名和行为不同；用 Python 生成默认值，
        SQLite 和 Postgres 表现完全一致。
    """
    return datetime.now(UTC).replace(tzinfo=None)


def new_uuid() -> str:
    """生成一个 36 位 UUID 字符串，用作业务表主键。

    用户、文档等程序创建的对象没有天然名字；UUID 不暴露数量、
    不易被猜出，多个服务/数据库合并时也不会撞号。
    """
    return str(uuid.uuid4())


class User(Base):
    """用户表：登录账号与权限角色。

    密码只存哈希，不存明文。校验时把用户输入的密码重新哈希后比对，
    即使数据库泄露也拿不到原始密码。
    """

    __tablename__ = "users"

    # 业务主键用 UUID；default=new_uuid 在插入时自动生成
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    # unique=True 会在数据库层建唯一索引：
    # 即使两个请求同时注册同名用户，也只有一个能成功。
    # index=True 让登录时按用户名查询走索引，不用全表扫描。
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    # 存 bcrypt 哈希（约 60 字符），长度留到 255 方便以后换算法
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 角色决定能访问哪些接口与文档：
    #   admin 管理用户/策略/审计；
    #   procurement / logistics / quality / finance 分别对应采购、物流、质量、财务视角。
    # 用字符串而不是数据库枚举：SQLite 对枚举支持弱，以后加角色不用迁移
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
