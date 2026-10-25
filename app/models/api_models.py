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


class GraphNode(BaseModel):
    """图谱节点。"""

    id: str
    name: str
    type: str
    risk_level: str | None = None
    region: str | None = None
    desc: str | None = None


class GraphLink(BaseModel):
    """图谱关系。"""

    source: str
    target: str
    relation: str
    detail: str = ""


class GraphPathLink(BaseModel):
    """影响路径中的一跳。"""

    source: str
    target: str
    relation: str


class GraphPath(BaseModel):
    """一条影响传导路径。"""

    rule: str
    rule_label: str
    severity: str
    reason: str
    hops: int
    summary: str
    nodes: list[GraphNode]
    links: list[GraphPathLink]
    affected: str


class AnswerRequest(BaseModel):
    """问答请求。"""

    question: str = Field(min_length=1, max_length=2000)
    model: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class AnswerResponse(BaseModel):
    """问答结果，hits 与 graph_paths 为回答所依据的证据。"""

    question: str
    answer: str
    reasoning: str | None = None
    model: str
    hits: list[ChunkHit]
    graph_paths: list[GraphPath] = Field(default_factory=list)


class ModelListResponse(BaseModel):
    """可选模型列表。"""

    models: list[str]
    default: str


class GraphOverviewResponse(BaseModel):
    """当前角色可见的子图。"""

    nodes: list[GraphNode]
    links: list[GraphLink]


class GraphImpactRequest(BaseModel):
    """图谱影响分析请求：问题与实体 ID 二选一。"""

    question: str | None = Field(default=None, max_length=2000)
    entity_id: str | None = None
    max_hops: int = Field(default=3, ge=1, le=4)


class GraphImpactResponse(BaseModel):
    """命中的实体与影响路径。"""

    entities: list[GraphNode]
    paths: list[GraphPath]


class GraphSeedResponse(BaseModel):
    """图谱导入结果。"""

    nodes: int
    relations: int
