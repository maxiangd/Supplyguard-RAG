"""摄取任务队列：把文档 ID 投递到 Redis RQ。"""

from redis import Redis
from rq import Queue

from app.core.configuration import settings

INGESTION_QUEUE_NAME = "ingestion"


def get_queue() -> Queue:
    """返回摄取队列。"""
    return Queue(INGESTION_QUEUE_NAME, connection=Redis.from_url(settings.redis_url))


def enqueue_document(document_id: str) -> None:
    """把文档摄取任务放入队列，worker 进程异步执行。"""
    # 延迟导入，避免 worker 模块与队列模块循环引用
    from app.workers.ingestion_worker import ingest_document

    get_queue().enqueue(ingest_document, document_id)