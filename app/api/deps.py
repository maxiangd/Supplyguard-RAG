"""FastAPI 依赖：从请求中解析当前用户。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, TokenPayload, decode_access_token
from app.db.models import User
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
    返回：TokenPayload，包含 user_id、role 与过期时间。
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
