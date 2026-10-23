"""认证路由：登录并签发访问令牌。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.models.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """登录：校验账号密码并签发 JWT。

    参数：
        payload —— 登录请求体，包含用户名和密码。
        db —— 数据库会话，由依赖注入提供。
    返回：TokenResponse，包含访问令牌与用户信息。
    异常：401 —— 账号或密码错误。
    """
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    token = create_access_token(user.user_id, role=user.role)

    return TokenResponse(
        access_token=token,
        user=UserOut(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
        ),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """返回当前登录用户的信息。

    参数：current_user —— 由 get_current_user 依赖解析出的用户。
    返回：UserOut，不含密码哈希。
    异常：401 —— 未提供令牌或令牌无效。
    """
    return UserOut(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
    )
