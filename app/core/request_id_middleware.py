"""请求 ID 中间件：为每个请求生成或透传唯一编号。"""

import re
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_VALID_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """把 request_id 写入日志上下文，并在响应头回传。"""

    async def dispatch(self, request: Request, call_next):
        """处理单个请求：确定 request_id、执行下游、回写响应头。"""
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex

        request.state.request_id = request_id
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
