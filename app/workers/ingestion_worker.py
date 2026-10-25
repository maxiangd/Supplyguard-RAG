"""RQ worker：解析、切块、向量化并写入 Qdrant。"""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from loguru import logger
from qdrant_client.models import PointStruct
from redis import Redis
from rq import Queue, SimpleWorker

from app.core.configuration import settings
from app.core.logging_setup import setup_logging
from app.db.database import SessionLocal
from app.db.tables import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_READY,
    Document,
    now_local,
)
from app.services.document_ingestion import extract_text, split_text
from app.services.embeddings import embed_texts
from app.services.ingestion_queue import INGESTION_QUEUE_NAME
from app.services.retrieval import (
    delete_document_points,
    ensure_collection,
    get_qdrant_client,
)


def ingest_document(document_id: str) -> None:
    """解析并向量化，成功置 ready、失败置 failed。"""
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            logger.warning("文档不存在，跳过摄取: {}", document_id)
            return

        document.status = DOCUMENT_STATUS_PROCESSING
        document.error_message = None
        session.commit()

        try:
            text = extract_text(Path(document.stored_path))
            chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
            if not chunks:
                raise ValueError("文档中没有可提取的文本")

            ensure_collection()
            vectors = embed_texts(chunks)

            client = get_qdrant_client()
            # 重新摄取时先删旧块，避免同一文档出现重复向量
            delete_document_points(document.document_id)
            client.upsert(
                collection_name=settings.qdrant_collection,
                points=[
                    PointStruct(
                        id=str(
                            uuid5(NAMESPACE_URL, f"{document.document_id}:{index}")
                        ),
                        vector=vector,
                        payload={
                            "document_id": document.document_id,
                            "filename": document.filename,
                            "chunk_index": index,
                            "text": chunk,
                            "allowed_roles": document.allowed_roles,
                            "uploaded_by": document.uploaded_by,
                        },
                    )
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors))
                ],
                wait=True,
            )

            document.chunk_count = len(chunks)
            document.status = DOCUMENT_STATUS_READY
            document.ingested_at = now_local()
        except Exception as exc:
            logger.exception("文档摄取失败: {}", document_id)
            document.status = DOCUMENT_STATUS_FAILED
            document.error_message = str(exc)[:500]

        session.commit()
        logger.info("文档摄取结束: {} -> {}", document_id, document.status)


def run_worker() -> None:
    """启动常驻 worker，监听摄取队列。"""
    setup_logging()
    connection = Redis.from_url(settings.redis_url)
    # Windows 不支持 fork，SimpleWorker 在子进程里直接执行任务
    worker = SimpleWorker(
        [Queue(INGESTION_QUEUE_NAME, connection=connection)],
        connection=connection,
    )
    logger.info("摄取 worker 已启动，队列 {}", INGESTION_QUEUE_NAME)
    worker.work()


if __name__ == "__main__":
    run_worker()