"""企业级中间件：RequestID / API Key 鉴权 / 限流（PROJECT_PLAN §10.1 / §11）。"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# 无需鉴权/限流的路径（健康检查、OpenAPI 文档）
_PUBLIC_PREFIXES = ("/v1/health", "/docs", "/openapi.json", "/redoc")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成/透传 request_id，并注入 structlog contextvars。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 鉴权。未配置 API_KEYS 时关闭（本地开发）。"""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if not settings.api_keys or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)
        key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not key:
            key = request.headers.get("X-API-Key", "").strip()
        if not key or key not in settings.api_keys:
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端地址的滑动窗口限流（默认 60 req/min）。"""

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.window_s = 60
        self.rate = settings.rate_limit_per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)
        client = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = time.monotonic()
        with self._lock:
            dq = self._hits[client]
            while dq and now - dq[0] > self.window_s:
                dq.popleft()
            if len(dq) >= self.rate:
                logger.warning("rate_limited", client=client, limit=self.rate)
                return JSONResponse(status_code=429, content={"detail": "rate limited"})
            dq.append(now)
        return await call_next(request)
