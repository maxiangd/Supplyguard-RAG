"""日志基础设施：使用 loguru 统一输出一行 JSON，并自动带上请求上下文。

loguru 负责日志的创建、级别和输出；本文件额外做三件事：
    1. 把标准库 logging（uvicorn、SQLAlchemy 等）的日志转发给 loguru；
    2. 把每条日志写成平铺 JSON，方便日志采集系统按字段检索；
    3. 从 ContextVar 注入 request_id 与当前用户。
"""

import json
import logging
import sys
import traceback
from datetime import UTC
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.log_context import get_request_id, get_user

# LogRecord 自带的内部字段。
# 桥接标准库日志时跳过这些字段，只保留调用方通过 extra={...} 附加的业务字段。
_STANDARD_RECORD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


def _inject_context(record: dict) -> None:
    """loguru patcher：在每条日志创建时补上请求上下文。

    参数：record —— loguru 的日志记录字典，直接原地修改。
    返回：None。
    """
    record["extra"].setdefault("request_id", get_request_id())
    record["extra"].setdefault("user", get_user())


def _json_sink(message: Any) -> None:
    """loguru sink：把一条日志写成平铺 JSON 到标准输出。

    参数：message —— loguru 的 Message 对象，message.record 是原始记录。
    返回：None。
    """
    record = message.record
    source_logger = record["extra"].pop("source_logger", None)
    payload: dict[str, Any] = {
        "timestamp": record["time"].astimezone(UTC).isoformat(timespec="milliseconds"),
        "level": record["level"].name,
        "logger": source_logger or record["name"],
        "message": record["message"],
    }
    # request_id、user 以及业务 extra 字段都平铺到第一层
    payload.update(record["extra"])

    if record["exception"] is not None:
        exc_type, exc_value, exc_tb = record["exception"]
        payload["exception"] = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )

    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


class InterceptHandler(logging.Handler):
    """把标准库 logging 的记录转发给 loguru。

    uvicorn、SQLAlchemy 等库只用标准库 logging，没有这层桥接，
    它们的日志会绕过 loguru，输出成另一种格式。
    """

    def emit(self, record: logging.LogRecord) -> None:
        """处理一条标准库日志记录。

        参数：record —— 标准库 LogRecord。
        返回：None。
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 找到真正调用日志的那一层，避免所有日志都显示成 InterceptHandler
        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_")
        }

        logger.bind(source_logger=record.name, **extra).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


def setup_logging() -> None:
    """配置 loguru 与标准库日志。应用启动时调用一次（create_app 里）。

    参数：无。
    返回：None。
    """
    # Windows 控制台默认按 GBK 输出，中文日志会乱码，统一改成 UTF-8。
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    # 去掉 loguru 默认的彩色输出，换成我们自己的 JSON sink
    logger.remove()
    logger.configure(patcher=_inject_context)
    logger.add(
        _json_sink,
        level=settings.log_level.upper(),
        backtrace=False,
        diagnose=False,
    )

    # 标准库日志全部交给 InterceptHandler，再统一走 loguru
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers = [InterceptHandler()]

    # uvicorn 会给自己挂 handler 并把 propagate 设为 False，这里清掉，
    # 让它的日志也走根 logger，保证格式统一。
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        std_logger = logging.getLogger(name)
        std_logger.handlers.clear()
        std_logger.propagate = True

    # 访问日志由我们自己的中间件记录，uvicorn 的重复信息压到 WARNING
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
