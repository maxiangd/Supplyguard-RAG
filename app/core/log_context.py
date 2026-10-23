"""请求上下文：用 ContextVar 保存 request_id 与当前用户，供日志读取。"""

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user: ContextVar[str | None] = ContextVar("user", default=None)


def set_request_id(value: str | None) -> Token:
    return _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def set_user(value: str | None) -> Token:
    return _user.set(value)


def get_user() -> str | None:
    return _user.get()


def reset_user(token: Token) -> None:
    _user.reset(token)