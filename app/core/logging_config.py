"""日志基础设施：所有日志统一输出成一行 JSON，并自动带上请求上下文。

Python logging 的四个角色（先分清楚，后面 code 才不会乱）：
    Logger    代码里的入口：logging.getLogger(__name__).info(...)
    Handler   日志写到哪里：控制台、文件、内存缓冲（后面监控页的环形缓冲也是 Handler）
    Formatter 一条日志长什么样：这里统一成 JSON
    Filter    哪些日志放行：本项目暂时不用，上下文由 Formatter 直接读取

为什么要输出 JSON？
    线上日志通常被采集系统（Loki / ELK）按字段索引。
    一行一个 JSON 对象，查 request_id 或 tenant_id 时可以直接按字段过滤，
    不用像文本日志那样写脆弱的正则。
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings
from app.core.log_context import get_request_id, get_tenant_id, get_user

# LogRecord 自带的内部字段。
# 格式化时要跳过它们，否则输出里会混进 pathname、thread 等一大堆我们不需要的细节；
# 只额外保留调用方通过 extra={...} 手动附加的自定义字段。
_STANDARD_RECORD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


class JsonFormatter(logging.Formatter):
    """把一条 LogRecord 转成一行 JSON 字符串。

    logging 每打一条日志都会调用 format(record)，
    返回值就是最终写到 Handler 上的文本。
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            # 用 UTC + 毫秒：服务部署在不同时区时，排错不会因为时差看错顺序
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            # getMessage() 已经完成过 %s 占位符替换，拿到的就是最终文本
            "message": record.getMessage(),
            # 下面三个值从 ContextVar 读取：
            # 日志在哪个请求里打出来，就自动带上哪个请求的上下文
            "request_id": get_request_id(),
            "user": get_user(),
            "tenant_id": get_tenant_id(),
        }

        # 调用方自定义字段，例如：
        #   logger.info("文档已入库", extra={"document_id": doc_id})
        # 这些字段会平铺进 JSON，方便按业务 id 检索。
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value

        # 异常堆栈单独放一个字段，message 里只保留一句话，
        # 这样日志采集系统仍能正常解析这一行 JSON。
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # ensure_ascii=False：中文原样输出，方便人直接看；
        # default=str：遇到 datetime 等 JSON 不认识的对象时转成字符串，避免格式化时抛错。
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """配置根 logger。应用启动时调用一次（create_app 里）。"""
    # Windows 控制台默认按 GBK 编码输出，中文日志会变成乱码。
    # 现代终端、IDE、Docker 都按 UTF-8 读取，所以把 stdout 统一改成 UTF-8。
    # reconfigure 不是所有类文件对象都有（例如 pytest 捕获输出时），拿不到就跳过。
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # 幂等处理：测试里可能反复创建 app，在同一个进程里多次调用本函数。
    # 先摘掉上次由我们自己挂上的 handler，避免同一条日志被输出两遍。
    # handler 是普通对象，允许动态加属性，这里用 _supplyguard 标记「是本项目挂的」。
    for handler in list(root.handlers):
        if getattr(handler, "_supplyguard", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._supplyguard = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    # uvicorn 启动时会给自己挂 handler 并把 propagate 设为 False，
    # 那样它的日志就会绕过我们的 JSON 格式，变成另一种样子的文本。
    # 清空它的 handler 并打开 propagate，让所有日志统一走根 logger。
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # 我们后面会写自己的请求日志中间件（记录方法、路径、状态码、耗时），
    # uvicorn 的 access log 会重复同样的信息，所以把它压到 WARNING 级别不再输出。
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
