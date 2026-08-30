"""FinCopilot FastAPI 应用入口。

分层：中间件（RequestID/Auth/RateLimit）→ API 路由 → 服务层 → Agent 图。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import AuthMiddleware, RateLimitMiddleware, RequestIDMiddleware

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """构造 FastAPI 应用（工厂模式，便于测试时注入配置）。"""
    settings = get_settings()
    setup_logging(settings.log_level)

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

    # 中间件（add 顺序 = 逆执行序，RequestID 最外层）
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # 挂载路由
    from app.api.chat import router as chat_router
    from app.api.health import router as health_router
    from app.api.threads import router as threads_router

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(threads_router)

    return app


app = create_app()
