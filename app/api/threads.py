"""线程 API：创建线程、拉取历史消息。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import thread_service

router = APIRouter(tags=["threads"])


@router.post("/v1/threads")
async def create_thread() -> dict:
    """创建新线程 → {thread_id}。"""
    thread_id = thread_service.create_thread()
    return {"thread_id": thread_id}


@router.get("/v1/threads/{thread_id}/messages")
async def get_messages(thread_id: str) -> dict:
    """拉取线程历史消息。"""
    messages = thread_service.list_messages(thread_id)
    if not messages:
        # 线程不存在（或尚无消息）
        raise HTTPException(status_code=404, detail="thread not found")
    return {"thread_id": thread_id, "messages": messages}
