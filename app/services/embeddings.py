"""文本向量化：调用阿里百炼的 OpenAI 兼容接口。"""

from functools import lru_cache

from openai import OpenAI

from app.core.configuration import settings

# 百炼 embedding 单次请求最多 10 条文本
EMBEDDING_BATCH_SIZE = 10


@lru_cache
def get_embedding_client() -> OpenAI:
    """返回共享的 embedding 客户端。"""
    return OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一批文本转成向量，顺序与输入一致。"""
    if not texts:
        return []

    client = get_embedding_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dimension,
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors
