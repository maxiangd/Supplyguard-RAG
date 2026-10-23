"""访问日志中间件：每个请求结束后输出一条结构化日志。

记录内容：HTTP 方法、路径、状态码、耗时、客户端 IP。
不记录：请求体、查询字符串、响应体。
    原因是请求体和查询串里可能有密码、token、文档内容，
    而日志会被采集和长期保存，泄露面比数据库更大。

级别选择：
    2xx/3xx → INFO
    4xx     → WARNING（客户端传错了，但服务本身没问题）
    5xx     → ERROR（服务端出问题，需要关注）
    健康检查 → DEBUG（探针每隔几秒就调一次，用 INFO 会把日志刷满）
"""

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# 这些路径调用频繁且信息量低，正常情况不需要出现在 INFO 日志里
_QUIET_PATHS = {"/api/health/live", "/api/health/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的处理结果，是排查"接口慢/报错"的第一手资料。"""

    async def dispatch(self, request: Request, call_next):
        """计时并记录一次请求。

        参数：
            request：当前请求。
            call_next：调用链中的下一个处理器。
        返回：
            下游返回的 Response；发生未捕获异常时记录堆栈后原样抛出。
        """
        # perf_counter 是单调时钟，适合测耗时，不受系统时间调整影响
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # 先记录完整堆栈，再把异常继续抛出，交给 FastAPI 返回 500
            logger.bind(
                source_logger="app.request",
                method=request.method,
                path=request.url.path,
                duration_ms=_elapsed_ms(start),
                client_ip=_client_ip(request),
            ).exception("请求处理异常")
            raise

        status = response.status_code
        path = request.url.path

        if path in _QUIET_PATHS:
            level = "DEBUG"
        elif status >= 500:
            level = "ERROR"
        elif status >= 400:
            level = "WARNING"
        else:
            level = "INFO"

        logger.bind(
            source_logger="app.request",
            method=request.method,
            path=path,
            status_code=status,
            duration_ms=_elapsed_ms(start),
            client_ip=_client_ip(request),
        ).log(level, "{} {} -> {}", request.method, path, status)
        return response


def _elapsed_ms(start: float) -> float:
    """计算从 start 到现在的毫秒数，保留两位小数。"""
    return round((time.perf_counter() - start) * 1000, 2)


def _client_ip(request: Request) -> str | None:
    """取客户端 IP；测试环境或某些传输方式下可能没有，此时返回 None。"""
    return request.client.host if request.client else None