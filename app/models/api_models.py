"""接口的请求与响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoleName = Literal["admin", "procurement", "logistics", "quality", "finance"]


class UserResponse(BaseModel):
    """返回给前端的用户信息，不含密码哈希。"""

    user_id: str
    username: str = Field(min_length=1, max_length=128)
    role: str
    is_active: bool


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CreateUserRequest(BaseModel):
    """管理员创建账号。"""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=72)
    role: RoleName


class UpdateUserRequest(BaseModel):
    """管理员修改账号角色或启用状态。"""

    role: RoleName | None = None
    is_active: bool | None = None


class DocumentResponse(BaseModel):
    """文档元信息与摄取状态。"""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    allowed_roles: list[str]
    uploaded_by: str
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime
    ingested_at: datetime | None


class DocumentChunkResponse(BaseModel):
    """文档切块内容。"""

    chunk_index: int
    text: str


class UpdateDocumentRolesRequest(BaseModel):
    """管理员调整文档的可访问角色。"""

    allowed_roles: list[RoleName] = Field(min_length=1)


class SearchRequest(BaseModel):
    """检索请求。"""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class ChunkHit(BaseModel):
    """检索命中的文档块。"""

    document_id: str
    filename: str
    chunk_index: int
    text: str
    allowed_roles: list[str]
    score: float


class SearchResponse(BaseModel):
    """检索结果。"""

    query: str
    hits: list[ChunkHit]
