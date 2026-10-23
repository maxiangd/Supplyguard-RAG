"""应用入口：创建 FastAPI、注册中间件与路由。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.request_id import RequestIDMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时初始化数据库，关闭时记录日志。"""
    init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建并配置应用，便于测试时创建多个实例。"""
    setup_logging()

    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.app_version,
        description="Supply chain risk AgentHarness with SecureRAG, GraphRAG and RBAC",
    )

    # 后添加的中间件在外层：CORS → RequestID → RequestLogging → 路由
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
    def liveness_check() -> dict:
        """存活探针，不检查外部依赖。"""
        return {"status": "ok", "environment": settings.env}

    logger.bind(env=settings.env, version=settings.app_version).info("应用已创建")
    return app


app = create_app()
