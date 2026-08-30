"""POST /v1/chat —— SSE 流式对话（PROJECT_PLAN §10.2）。"""

from __future__ import annotations

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/v1/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    """流式对话。SSE 事件：meta → step* → delta* → sources → done。"""

    async def event_gen():
        async for ev in chat_service.stream_chat(req):
            yield ev.to_sse()

    return EventSourceResponse(event_gen())
