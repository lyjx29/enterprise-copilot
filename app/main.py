"""FinCopilot FastAPI 应用入口。

M0 骨架：lifespan 管理生命周期 + 健康检查路由。
后续里程碑在 lifespan 中挂载 Qdrant 客户端、LangGraph 图等资源。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """构造 FastAPI 应用（工厂模式，便于测试时注入配置）。"""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("app_startup", app=settings.app_name, version=settings.version)
        yield
        logger.info("app_shutdown")

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # 挂载路由
    from app.api.health import router as health_router

    app.include_router(health_router)

    return app


app = create_app()
