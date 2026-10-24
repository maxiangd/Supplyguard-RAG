"""用户管理路由：管理员查看、创建与停用账号。"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.security import hash_password
from app.db.database import get_database_session
from app.db.tables import User
from app.models.api_models import CreateUserRequest, UpdateUserRequest, UserResponse

# 同一个依赖实例：路由级校验和函数内取当前用户共用，FastAPI 每次请求只执行一次
admin_only = require_roles("admin")

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(admin_only)],
)


def _to_response(user: User) -> UserResponse:
    """把 ORM 用户转成响应模型。"""
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
    )


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_database_session)) -> list[UserResponse]:
    """列出全部账号。"""
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [_to_response(user) for user in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest, db: Session = Depends(get_database_session)
) -> UserResponse:
    """创建账号，用户名不可重复。"""
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已存在"
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    user = User(
        username=payload.username,
        password_hash=password_hash,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    db: Session = Depends(get_database_session),
    current_user: User = Depends(admin_only),
) -> UserResponse:
    """修改账号角色或启用状态。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在"
        )
    if payload.role is None and payload.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="没有需要修改的字段"
        )
    if user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改当前登录账号的角色或状态",
        )

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_database_session),
    current_user: User = Depends(admin_only),
) -> Response:
    """删除账号，不能删除当前登录账号。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在"
        )
    if user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录账号",
        )

    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
