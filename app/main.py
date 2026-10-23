import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.request_id import RequestIDMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from app.db.init_db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时记录日志。

    参数：_app —— FastAPI 注入的应用实例，本函数暂不使用。
    返回：异步生成器；yield 之前是启动逻辑，之后是关闭逻辑。
    """
    init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    返回：配置好中间件和路由的应用对象。
    之所以用工厂函数而不是模块级一次配置，是为了测试时能独立创建多个应用。
    """
    # 日志必须在应用创建前配置好，否则启动早期的日志会用默认格式
    setup_logging()

    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.app_version,
        description="Supply chain risk AgentHarness with SecureRAG, GraphRAG and RBAC",
    )

    # Starlette 的规则：后添加的中间件在更外层。
    # 先加 RequestLogging、后加 RequestID，实际执行顺序是：
    #   RequestID 先生成/写入请求 ID → RequestLogging 开始计时并记日志 → 路由
    # 这个顺序不能反：RequestLogging 打日志时需要拿到 RequestID 已写好的上下文。
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=settings.api_prefix)

    @app.get("/api/health/live", tags=["health"])
    def live() -> dict:
        """存活探针：进程还在跑就返回 200。

        只证明"应用能响应请求"，不检查数据库、Qdrant 等外部依赖，
        所以容器编排系统用它判断是否需要重启进程。
        """
        return {"status": "ok", "environment": settings.env}

    logger.info("应用已创建", extra={"env": settings.env, "version": settings.app_version})
    return app


# uvicorn 的入口变量：uvicorn app.main:app
app = create_app()
