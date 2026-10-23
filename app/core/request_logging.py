"""访问日志中间件：记录方法、路径、状态码、耗时与客户端 IP。

不记录请求体和查询串，避免密码、token、文档内容进入日志。
"""

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_QUIET_PATHS = {"/api/health/live", "/api/health/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
    return round((time.perf_counter() - start) * 1000, 2)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None