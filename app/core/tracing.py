"""Langfuse tracing（可选，LANGFUSE_ENABLED=true 时启用，ADR-6）。

默认关闭且不引入 langfuse 依赖；开启时延迟 import。
"""

from __future__ import annotations

from app.core.config import get_settings

_handler = None


def get_langfuse_handler():
    """返回 Langfuse CallbackHandler；未启用时返回 None。"""
    global _handler
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    if _handler is None:
        from langfuse.callback import CallbackHandler

        _handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _handler
