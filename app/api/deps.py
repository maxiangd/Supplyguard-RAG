"""FastAPI 依赖：从请求中解析当前用户与租户上下文。"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenError, TokenPayload, decode_access_token
from app.db.models import User, UserTenant
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    """构造统一的 401 响应，并附带 Bearer 认证头。

    参数：detail —— 返回给客户端的错误说明。
    返回：HTTPException 实例，由调用方 raise。
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    """解析 Authorization 头中的 JWT。

    参数：credentials —— HTTPBearer 解析出的凭证，未提供时为 None。
    返回：TokenPayload，包含 user_id、role、tenant_id 与过期时间。
    异常：401 —— 未提供令牌、签名错误、已过期或格式非法。
    """
    if credentials is None:
        raise _unauthorized("未提供访问令牌")

    try:
        return decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc


def get_current_user(
    payload: TokenPayload = Depends(get_current_payload),
    db: Session = Depends(get_db),
) -> User:
    """加载令牌对应的用户，确认账号仍然存在。

    参数：
        payload —— 已解析的令牌内容。
        db —— 数据库会话，由依赖注入提供。
    返回：User ORM 对象。
    异常：401 —— 令牌中的用户已被删除。
    """
    user = db.get(User, payload.user_id)
    if user is None:
        raise _unauthorized("用户不存在或已被删除")
    return user


def get_current_tenant_id(
    payload: TokenPayload = Depends(get_current_payload),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    header_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """确定并校验当前租户。

    优先级：X-Tenant-ID 请求头 > 令牌中的租户 > 用户默认租户。
    参数：
        payload —— 令牌内容。
        user —— 当前用户。
        db —— 数据库会话。
        header_tenant_id —— 前端切换租户时携带的请求头。
    返回：经过成员关系校验的租户 ID。
    异常：
        400 —— 无法确定租户。
        403 —— 用户不是该租户成员。
    """
    tenant_id = header_tenant_id or payload.tenant_id or user.default_tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未指定租户",
        )

    member = db.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user.user_id,
            UserTenant.tenant_id == tenant_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该租户",
        )
    return tenant_id


def require_roles(*roles: str):
    """生成角色校验依赖，只允许指定角色通过。

    参数：roles —— 允许的角色名，例如 require_roles("admin")。
    返回：依赖函数；用法：current_user: User = Depends(require_roles("admin"))。
    异常：403 —— 当前用户角色不在允许列表中。
    """

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user

    return checker