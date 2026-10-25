"""Qdrant 检索：向量化查询并按角色过滤文档块。"""

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    VectorParams,
)

from app.core.configuration import settings
from app.services.embeddings import embed_texts

ROLE_PAYLOAD_FIELD = "allowed_roles"
DOCUMENT_PAYLOAD_FIELD = "document_id"


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


def document_filter(document_id: str) -> Filter:
    """按文档 ID 定位其全部向量块。"""
    return Filter(
        must=[
            FieldCondition(
                key=DOCUMENT_PAYLOAD_FIELD, match=MatchValue(value=document_id)
            )
        ]
    )


def delete_document_points(document_id: str) -> None:
    """删除文档的全部向量块，重新摄取前也用它清理旧块。"""
    get_qdrant_client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=document_filter(document_id),
        wait=True,
    )


def sync_document_roles(document_id: str, roles: list[str]) -> None:
    """把新的角色白名单写回已入库向量，保证检索过滤立即生效。"""
    get_qdrant_client().set_payload(
        collection_name=settings.qdrant_collection,
        payload={ROLE_PAYLOAD_FIELD: roles},
        points=document_filter(document_id),
        wait=True,
    )


def list_document_chunks(document_id: str) -> list[dict]:
    """按块序号返回某文档的全部切块内容。"""
    points, _ = get_qdrant_client().scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=document_filter(document_id),
        limit=1000,
        with_payload=True,
    )
    chunks = [dict(point.payload or {}) for point in points]
    chunks.sort(key=lambda chunk: chunk.get("chunk_index", 0))
    return chunks


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
