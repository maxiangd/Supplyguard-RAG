"""Qdrant 检索：向量化查询并按角色过滤文档块。"""

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, VectorParams

from app.core.configuration import settings
from app.services.embeddings import embed_texts

ROLE_PAYLOAD_FIELD = "allowed_roles"


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """返回共享的 Qdrant 客户端。"""
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    """集合不存在时按配置的维度创建。"""
    client = get_qdrant_client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimension, distance=Distance.COSINE
            ),
        )


def search_chunks(query: str, role: str, top_k: int) -> list[dict]:
    """检索当前角色可访问的文档块，管理员不加过滤。"""
    vector = embed_texts([query])[0]

    query_filter = None
    if role != "admin":
        query_filter = Filter(
            must=[
                FieldCondition(key=ROLE_PAYLOAD_FIELD, match=MatchAny(any=[role]))
            ]
        )

    response = get_qdrant_client().query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    hits = []
    for point in response.points:
        payload = dict(point.payload or {})
        payload["score"] = point.score
        hits.append(payload)
    return hits
