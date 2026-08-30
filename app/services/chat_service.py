"""聊天编排：组装 state → 图流式执行 → 转 SSE 事件流 → 落库。

SSE 事件序列（PROJECT_PLAN §10.2）：meta → step* → delta* → sources → done。
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage

from app.core.config import get_settings
from app.core.tracing import get_langfuse_handler
from app.schemas.chat import ChatRequest, SSEEvent
from app.services import thread_service

_graph_instance = None


async def get_graph():
    """编译好的分层多 Agent 图（进程内单例，AsyncSqliteSaver 记忆）。"""
    global _graph_instance
    if _graph_instance is None:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        from app.agents.graph import build_graph

        settings = get_settings()
        conn = await aiosqlite.connect(settings.checkpoint_db_path)
        _graph_instance = build_graph(checkpointer=AsyncSqliteSaver(conn))
    return _graph_instance


async def stream_chat(req: ChatRequest) -> AsyncIterator[SSEEvent]:
    """流式执行一次对话，产出 SSE 事件。"""
    settings = get_settings()
    graph = await get_graph()
    thread_id = req.thread_id or uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    # Langfuse tracing（可选）：开启时挂 callback
    handler = get_langfuse_handler()
    if handler is not None:
        config["callbacks"] = [handler]
    state = {"messages": [HumanMessage(content=req.question)]}

    yield SSEEvent(
        event="meta",
        data={"thread_id": thread_id, "route": "pending", "model": settings.llm_model},
    )

    start = time.monotonic()
    answer_parts: list[str] = []
    sources: list[dict] = []
    route: str = "rag"

    try:
        async for mode, payload in graph.astream(
            state, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                chunk, _meta = payload
                # 只流式分支 agent（rag/sql/web）的回答 token，跳过 supervisor 的结构化 JSON
                node = _meta.get("langgraph_node") if isinstance(_meta, dict) else None
                if node == "supervisor":
                    continue
                text = getattr(chunk, "content", "")
                if text:
                    yield SSEEvent(event="delta", data={"content": text})
                    answer_parts.append(text)
            elif mode == "updates":
                for node, update in payload.items():
                    if node == "supervisor":
                        route = update.get("datasource", route)
                        yield SSEEvent(event="step", data={"type": "route", "detail": route})
                    elif isinstance(update, dict) and update.get("sources"):
                        sources = update["sources"]
                        yield SSEEvent(
                            event="step",
                            data={"type": "done_branch", "detail": node, "sources": sources},
                        )
    except Exception:
        yield SSEEvent(event="error", data={"message": "内部错误", "code": "INTERNAL"})
        # 仍返回已产出的部分（不抛给客户端）
        return

    latency_ms = int((time.monotonic() - start) * 1000)
    answer = "".join(answer_parts)

    yield SSEEvent(event="sources", data={"sources": sources})

    # 落库（生成完成时才写，流中断不落半截）
    thread_service.add_message(thread_id, "user", req.question)
    message_id = thread_service.add_message(thread_id, "assistant", answer, sources)

    yield SSEEvent(
        event="done",
        data={"message_id": message_id, "latency_ms": latency_ms},
    )
