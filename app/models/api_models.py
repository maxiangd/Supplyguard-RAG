"""接口的请求与响应模型。"""

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """返回给前端的用户信息，不含密码哈希。"""

    user_id: str
    username: str = Field(min_length=1, max_length=128)
    role: str


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
