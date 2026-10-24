"""FastAPI 依赖：解析当前用户与角色。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, TokenPayload, decode_access_token
from app.db.database import get_database_session
from app.db.tables import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    """构造带 WWW-Authenticate 头的 401 响应。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    """解析 Authorization 头中的 JWT。"""
    if credentials is None:
        raise _unauthorized("未提供访问令牌")
    try:
        return decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc


def get_current_user(
    payload: TokenPayload = Depends(get_token_payload),
    db: Session = Depends(get_database_session),
) -> User:
    """加载令牌对应的用户。"""
    user = db.get(User, payload.user_id)
    if user is None:
        raise _unauthorized("用户不存在")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用"
        )
    return user


def require_roles(*roles: str):
    """只允许指定角色访问。"""

    def role_checker(user: User = Depends(get_current_user)) -> User:
        """校验用户角色是否在允许列表中。"""
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
            )
        return user

    return role_checker