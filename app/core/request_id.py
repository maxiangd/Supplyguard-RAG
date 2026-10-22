"""请求 ID 中间件：给每个 HTTP 请求确定一个唯一编号。

编号从哪来？
    优先使用客户端传来的 X-Request-ID（方便前端或网关串联调用链），
    没有或格式不合法时，由服务端生成一个随机 ID。

编号拿来做什么？
    1. 写进 ContextVar，下游所有日志自动带上它；
    2. 回写到响应头，用户报错时可以把编号给你，直接检索日志；
    3. 写进 request.state，路由里需要时可直接读取。
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.log_context import reset_request_id, set_request_id

# 入站请求 ID 只接受这个格式：字母/数字/点/下划线/冒号/连字符，最长 64。
# 为什么要校验？
#   请求头完全由客户端控制。恶意客户端可能塞入超长字符串、换行符等，
#   虽然 JSON 序列化会转义换行，但限制格式能让日志保持干净，
#   也避免有人伪造别人的请求 ID 来混淆排查。
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求确定 request_id，并在请求结束时清理上下文。

    继承 BaseHTTPMiddleware 后，只需实现 dispatch：
    在调用下游应用前做准备，在响应返回后做收尾。
    """

    async def dispatch(self, request: Request, call_next):
        """处理单个请求。

        参数：
            request：当前请求，可以读取请求头和 URL。
            call_next：调用链中的下一个处理器（后面可能是别的中间件或路由）。
        返回：
            Starlette 的 Response，并额外带上 X-Request-ID 响应头。
        """
        incoming = request.headers.get("X-Request-ID", "")
        if _VALID_REQUEST_ID.match(incoming):
            request_id = incoming
        else:
            # uuid4().hex 是 32 位十六进制随机串，重复概率可忽略
            request_id = uuid.uuid4().hex

        # 写入 ContextVar。之后在本请求内任何地方打的日志都会带上它。
        token = set_request_id(request_id)
        # 同时挂到 request.state，路由函数可通过 request.state.request_id 读取
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            # 不管成功还是抛异常，都要复位上下文。
            # 否则这个执行上下文被复用时，下一条日志可能带着上一个请求的 ID。
            #
            # 已知限制：流式响应（后面的 /chat/stream SSE）在 call_next 返回响应头后
            # 才逐块发送 body，此时上下文已经复位，流内部的日志可能读不到 request_id。
            # 等实现流式问答时会改用 ASGI 中间件，或把 ID 显式传进去。
            reset_request_id(token)

        # 回写给客户端：出了问题，用户可以直接报这个编号
        response.headers["X-Request-ID"] = request_id
        return response
