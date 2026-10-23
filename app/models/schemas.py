"""请求与响应模型（Pydantic）：约束接口的输入输出形状。"""

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    """返回给前端的用户信息，不包含密码哈希。"""

    user_id: str
    username: str = Field(min_length=1, max_length=128)
    role: str


class LoginRequest(BaseModel):
    """登录请求：账号与密码。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """登录成功响应：JWT、令牌类型与用户信息。"""

    access_token: str
    token_type: str = "bearer"
    user: UserOut
