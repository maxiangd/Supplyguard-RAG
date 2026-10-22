"""请求上下文：把「当前请求是谁、来自哪个租户、请求 ID 是什么」存进 ContextVar。

为什么需要它？
    日志、审计、错误处理都想知道「这条日志属于哪个请求」，
    但我们不可能把 request_id 作为参数一路传到每个函数里。
    ContextVar 提供了一个隐式的、按执行上下文隔离的存储。

为什么不用全局变量？
    FastAPI 会同时处理多个请求。全局变量会被并发请求互相覆盖
    （A 请求刚写入自己的 ID，B 请求立刻把它改掉）；
    ContextVar 是「每个执行上下文各有一份」，天然隔离。

为什么不用 threading.local？
    本地开发时 FastAPI 会把同步路由丢进线程池、异步路由跑在事件循环里；
    threading.local 在 async 任务切换时无法正确隔离，ContextVar 两者都支持。

注意：ContextVar 里的值不会自动跨线程传递。
    以后 LangGraph 工作流会用 ThreadPoolExecutor 跑同步图，
    在那种线程里读到的 request_id 会是 None —— 到时候需要显式复制上下文。
"""

from contextvars import ContextVar, Token

# default=None 表示「当前不在请求里」（例如应用启动阶段、后台任务）。
# 用 None 而不是空字符串，是为了让「没有请求上下文」和「请求 ID 恰好为空」可区分。
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user: ContextVar[str | None] = ContextVar("user", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def set_request_id(value: str | None) -> Token:
    """把当前请求的 ID 写入上下文。

    参数：
        value：本次请求的 ID，通常由中间件生成或从请求头 X-Request-ID 读取。
    返回：
        Token，请求结束时传给 reset_request_id() 恢复原值。
    """
    return _request_id.set(value)


def get_request_id() -> str | None:
    """读取当前请求的 ID；不在请求内（启动阶段、后台线程）时返回 None。"""
    return _request_id.get()


def reset_request_id(token: Token) -> None:
    """用 set_request_id() 返回的 token 恢复成写入之前的值。

    中间件在 finally 里调用，防止请求间上下文串味。
    """
    _request_id.reset(token)


def set_user(value: str | None) -> Token:
    """把当前登录用户名写入上下文，供日志和审计使用。

    通常在鉴权依赖（get_current_user）解析出用户后调用。
    返回 token，用于请求结束时复位。
    """
    return _user.set(value)


def get_user() -> str | None:
    """读取当前登录用户名；未登录或无请求上下文时返回 None。"""
    return _user.get()


def reset_user(token: Token) -> None:
    """用 set_user() 返回的 token 恢复上下文中的用户值。"""
    _user.reset(token)


def set_tenant_id(value: str | None) -> Token:
    """把当前租户 ID 写入上下文，日志据此区分数据归属。

    多租户系统里排查问题经常需要"只看某个租户"的日志，
    所以租户要和请求 ID 一样贯穿整个请求。
    """
    return _tenant_id.set(value)


def get_tenant_id() -> str | None:
    """读取当前租户 ID；无请求上下文时返回 None。"""
    return _tenant_id.get()


def reset_tenant_id(token: Token) -> None:
    """用 set_tenant_id() 返回的 token 恢复上下文中的租户值。"""
    _tenant_id.reset(token)
