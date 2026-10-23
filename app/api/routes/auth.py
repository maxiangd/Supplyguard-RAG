"""认证路由：登录并签发访问令牌。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.models import User, UserTenant
from app.db.session import get_db
from app.models.schemas import LoginRequest, TokenResponse, UserOut


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """登录：校验账号密码与租户成员关系，签发 JWT。

    参数：
        payload —— 登录请求体，包含用户名、密码和可选租户。
        db —— 数据库会话，由依赖注入提供。
    返回：TokenResponse，包含访问令牌、生效租户与用户信息。
    异常：
        401 —— 账号或密码错误。
        403 —— 用户不是该租户成员。
        400 —— 用户没有可用租户。
    """
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    tenant_id = payload.tenant_id or user.default_tenant_id
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未分配租户",
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

    token = create_access_token(user.user_id, role=user.role, tenant_id=tenant_id)

    return TokenResponse(
        access_token=token,
        tenant_id=tenant_id,
        user=UserOut(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            default_tenant_id=user.default_tenant_id,
        ),
    )
