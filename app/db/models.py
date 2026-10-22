"""数据库表模型（ORM）。

ORM 的意思是：用 Python 类描述数据库表，
    类  = 一张表
    属性 = 一列
    实例 = 一行数据

目前只有 tenants 一张表，后续会按批次逐步加入 users、documents 等。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow_naive() -> datetime:
    """返回当前 UTC 时间的 naive datetime（不带时区信息）。

    为什么不带时区？
        SQLite 不保存时区，Postgres 的 DateTime 也不带时区。
        如果有的地方存带时区、有的地方存不带，读出来会混。
        统一规则：存 UTC 的 naive 时间，展示时再由前端/接口转成本地时间。

    为什么不用数据库的 NOW()？
        各数据库函数名和行为不同；用 Python 生成默认值，
        SQLite 和 Postgres 表现完全一致。
    """
    return datetime.now(UTC).replace(tzinfo=None)


def new_uuid() -> str:
    """生成一个 36 位 UUID 字符串，用作业务表主键。

    为什么用户、文档等用 UUID，而租户用可读字符串？
        用户、文档是程序创建的对象，没有天然名字；UUID 不暴露数量、
        不易被猜出，多个服务/数据库合并时也不会撞号。
        租户则要出现在 token、日志、配置里，可读性更重要。
    """
    return str(uuid.uuid4())


class Tenant(Base):
    """租户表：多租户系统里最上层的隔离单位。

    可以理解成一个"公司"或"部门"。用户、文档、审批单、审计记录
    都会带 tenant_id，查询时按它过滤，保证不同租户的数据互不可见。
    """

    __tablename__ = "tenants"

    # tenant_id 是主键，用字符串而不是自增整数，原因：
    #   1. 它会写进 JWT、Qdrant payload、审计日志，可读的字符串便于排查
    #   2. 不依赖数据库自增，迁移或换库时编号不会变
    #   3. 长度限制 64 足够，且能防止意外的超长值
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 展示名称，例如"演示租户"、"Acme 公司"，只用于界面显示，不参与逻辑判断
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 创建时间。default=utcnow_naive 表示由 Python 在插入时自动填值；
    # nullable=False 保证每条记录都有时间，不会出现空值排序问题
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


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

    # 角色决定能访问哪些接口：admin 可管理用户/租户/监控，user 只能问答和查看自己的数据。
    # 用字符串而不是数据库枚举：SQLite 对枚举支持弱，字符串更简单，以后加角色不用迁移
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")

    # 默认租户：登录后如果请求没带 X-Tenant-ID，就用它。
    # 允许为空：用户可能还没被分配任何租户，此时登录后由接口返回提示。
    # ForeignKey 保证这个值一定指向真实存在的租户。
    default_tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )


class UserTenant(Base):
    """用户-租户成员表：记录"谁可以访问哪个租户"。

    为什么需要单独一张表？
        一个用户可以属于多个租户，一个租户也有多个用户，这是多对多关系。
        多对多无法用外键直接表达，标准做法就是中间表：
        每一行代表一条"成员关系"。
    """

    __tablename__ = "user_tenants"
    __table_args__ = (
        # 同一对 (user_id, tenant_id) 只能出现一次，
        # 防止管理员重复把同一个人加进同一个租户
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
        # 两个查询方向都会用到：查"我有哪些租户"、查"这个租户有哪些人"，
        # 所以两边都建索引
        Index("ix_user_tenants_user_id", "user_id"),
        Index("ix_user_tenants_tenant_id", "tenant_id"),
    )

    # 代理主键：这张表本身没有天然的唯一标识，自增整数最简单。
    # 业务上的唯一性由上面的 UniqueConstraint 保证。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ondelete="CASCADE"：删除用户时，数据库自动删掉他的成员关系，
    # 不会留下指向已删除用户的孤儿记录。
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
