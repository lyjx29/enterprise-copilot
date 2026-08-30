"""对话 API 的请求/响应模型（PROJECT_PLAN §10）。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /v1/chat 请求体。"""

    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    thread_id: str | None = Field(default=None, description="会话 ID；不传则新建")
    stream: bool = Field(default=True, description="是否 SSE 流式返回")


class SSEEvent(BaseModel):
    """SSE 事件（event + data）。data 序列化为 JSON。"""

    event: str
    data: dict[str, Any]

    def to_sse(self) -> dict[str, Any]:
        """sse-starlette 的 data 需为 JSON 字符串（dict 会输出 repr）。"""
        return {"event": self.event, "data": json.dumps(self.data, ensure_ascii=False)}
