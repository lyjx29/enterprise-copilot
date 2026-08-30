"""健康检查端点。

- GET /v1/health        存活探针（liveness）
- GET /v1/health/ready  就绪探针（readiness）——检查 Qdrant / 员工库依赖
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/v1/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "version": settings.version}


@router.get("/v1/health/ready")
async def health_ready() -> dict:
    """就绪检查：Qdrant 可达 + 员工库文件存在。任一依赖不可用返回 degraded。"""
    settings = get_settings()
    deps: dict[str, str] = {}

    # Qdrant
    try:
        from app.tools.retrieval import get_qdrant_client

        get_qdrant_client(settings).get_collections()
        deps["qdrant"] = "ok"
    except Exception:
        deps["qdrant"] = "unavailable"

    # 员工库（SQLite 只读 URI 里的路径）
    try:
        db_path = settings.employees_db_uri.replace("sqlite:///", "", 1)
        deps["database"] = "ok" if Path(db_path).exists() else "missing"
    except Exception:
        deps["database"] = "unknown"

    status = "ready" if all(v == "ok" for v in deps.values()) else "degraded"
    return {"status": status, "version": settings.version, "dependencies": deps}
