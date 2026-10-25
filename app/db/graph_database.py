"""Neo4j 连接：进程内共享驱动，按需开启会话执行 Cypher。"""

from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.core.configuration import settings


@lru_cache
def get_graph_driver() -> Driver:
    """返回共享驱动，连接池由驱动内部维护。"""
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def run_query(cypher: str, parameters: dict | None = None) -> list[dict]:
    """执行只读查询，返回每行记录转换后的字典列表。"""
    with get_graph_driver().session(database=settings.neo4j_database) as session:
        result = session.run(cypher, parameters or {})
        return [record.data() for record in result]


def run_write(cypher: str, parameters: dict | None = None) -> None:
    """执行写查询，交给托管事务处理重试。"""
    with get_graph_driver().session(database=settings.neo4j_database) as session:
        session.execute_write(
            lambda transaction: transaction.run(cypher, parameters or {}).consume()
        )


def graph_is_ready() -> bool:
    """健康检查用：Neo4j 不可达时返回 False 而不是抛异常。"""
    try:
        get_graph_driver().verify_connectivity()
        return True
    except Exception:
        return False
