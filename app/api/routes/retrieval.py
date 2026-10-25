"""检索路由：按当前角色返回可访问的文档块。"""

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAIError

from app.api.dependencies import get_current_user
from app.core.configuration import settings
from app.db.tables import User
from app.models.api_models import ChunkHit, SearchRequest, SearchResponse
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
def search_documents(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """检索当前角色可见的文档块。"""
    try:
        hits = search_chunks(
            payload.query,
            current_user.role,
            payload.top_k or settings.top_k,
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="向量服务不可用，请检查 APP_EMBEDDING_API_KEY",
        ) from exc

    return SearchResponse(
        query=payload.query,
        hits=[ChunkHit(**hit) for hit in hits],
    )