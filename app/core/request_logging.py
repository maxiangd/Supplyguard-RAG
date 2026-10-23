"""访问日志中间件：记录方法、路径、状态码、耗时与客户端 IP。

不记录请求体和查询串，避免密码、token、文档内容进入日志。
"""

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_QUIET_PATHS = {"/api/health/live", "/api/health/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的方法、路径、状态码、耗时与客户端 IP。"""

    async def dispatch(self, request: Request, call_next):
        """执行下游请求并按状态码选择日志级别。"""
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
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
    """计算从 start 到现在的毫秒数。"""
    return round((time.perf_counter() - start) * 1000, 2)


def _client_ip(request: Request) -> str | None:
    """返回客户端 IP，取不到时返回 None。"""
    return request.client.host if request.client else None