"""应用入口：创建 FastAPI、注册中间件与路由。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.approvals import router as approvals_router
from app.api.routes.audit import router as audit_router
from app.api.routes.authentication import router as auth_router
from app.api.routes.benchmark import router as benchmark_router
from app.api.routes.chat import router as chat_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.documents import router as documents_router
from app.api.routes.graph import router as graph_router
from app.api.routes.memory import router as memory_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.users import router as users_router
from app.core.configuration import settings
from app.core.logging_setup import setup_logging
from app.core.request_id_middleware import RequestIDMiddleware
from app.core.request_logging_middleware import RequestLoggingMiddleware
from app.db.initialize_database import init_db


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
    app.include_router(users_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(retrieval_router, prefix=settings.api_prefix)
    app.include_router(graph_router, prefix=settings.api_prefix)
    app.include_router(chat_router, prefix=settings.api_prefix)
    app.include_router(approvals_router, prefix=settings.api_prefix)
    app.include_router(audit_router, prefix=settings.api_prefix)
    app.include_router(memory_router, prefix=settings.api_prefix)
    app.include_router(benchmark_router, prefix=settings.api_prefix)
    app.include_router(dashboard_router, prefix=settings.api_prefix)

    @app.get("/api/health/live", tags=["health"])
    def liveness_check() -> dict:
        """存活探针，不检查外部依赖。"""
        return {"status": "ok", "environment": settings.env}

    logger.bind(env=settings.env, version=settings.app_version).info("应用已创建")
    return app



app = create_app()
