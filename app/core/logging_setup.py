"""日志：loguru 统一输出平铺 JSON，请求内自动带 request_id。"""

import json
import logging
import sys
import traceback
from typing import Any

from loguru import logger

from app.core.configuration import settings

_STANDARD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


def _json_sink(message: Any) -> None:
    """把一条 loguru 日志写成平铺 JSON 输出到终端。"""
    record = message.record
    source_logger = record["extra"].pop("source_logger", None)
    payload: dict[str, Any] = {
        "timestamp": record["time"]
        .replace(tzinfo=None)
        .isoformat(timespec="milliseconds"),
        "level": record["level"].name,
        "logger": source_logger or record["name"],
        "message": record["message"],
    }
    payload.update(record["extra"])

    if record["exception"]:
        payload["exception"] = "".join(
            traceback.format_exception(*record["exception"])
        )

    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


class InterceptHandler(logging.Handler):
    """把标准库 logging 的记录转发给 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        """处理一条标准库日志记录。"""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_FIELDS and not key.startswith("_")
        }
        logger.bind(source_logger=record.name, **extra).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


def setup_logging() -> None:
    """配置 loguru 与标准库日志，应用启动时调用一次。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")

    logger.remove()
    logger.add(_json_sink, level=settings.log_level.upper())

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers = [InterceptHandler()]

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        std_logger = logging.getLogger(name)
        std_logger.handlers.clear()
        std_logger.propagate = True

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)