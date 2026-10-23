"""认证路由：登录并签发访问令牌。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_database_session
from app.models.schemas import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, db: Session = Depends(get_database_session)
) -> TokenResponse:
    """校验账号密码并签发 JWT。"""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    token = create_access_token(user.user_id, role=user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
        ),
    )


@router.get("/current-user", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """返回当前登录用户。"""
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
    )