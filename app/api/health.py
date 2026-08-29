"""健康检查端点。

- GET /v1/health        存活探针（liveness）
- GET /v1/health/ready  就绪探针（readiness）——M3 起检查 Qdrant / DB 依赖
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/v1/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "version": settings.version}


@router.get("/v1/health/ready")
async def health_ready() -> dict:
    """就绪检查：骨架阶段返回基础状态，依赖检查在 M3 补齐。"""
    settings = get_settings()
    return {
        "status": "ready",
        "version": settings.version,
        "dependencies": {
            "qdrant": "pending",  # M3: 改为实际探活
            "database": "pending",  # M3: 改为实际探活
        },
    }
