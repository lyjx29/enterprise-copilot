"""M2 冒烟测试：线程 API + SSE 事件协议（离线可跑，chat 用 mock 流）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_thread() -> None:
    resp = client.post("/v1/threads")
    assert resp.status_code == 200
    assert "thread_id" in resp.json()


def test_chat_sse_protocol(monkeypatch) -> None:
    """验证 /v1/chat 输出符合 SSE 协议（meta→delta→sources→done）。"""
    from app.schemas.chat import SSEEvent

    async def fake_stream(req):
        yield SSEEvent(event="meta", data={"thread_id": "t1", "route": "rag", "model": "qwen3"})
        yield SSEEvent(event="step", data={"type": "route", "detail": "rag"})
        yield SSEEvent(event="delta", data={"content": "Answer part 1 "})
        yield SSEEvent(event="delta", data={"content": "Answer part 2"})
        yield SSEEvent(event="sources", data={"sources": [{"company": "amazon"}]})
        yield SSEEvent(event="done", data={"message_id": "m-1", "latency_ms": 10})

    monkeypatch.setattr("app.api.chat.chat_service.stream_chat", fake_stream)

    resp = client.post("/v1/chat", json={"question": "hi", "thread_id": "t1"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    body = resp.text
    assert "event: meta" in body
    assert "event: step" in body
    assert "event: delta" in body
    assert "Answer part 1" in body
    assert "Answer part 2" in body
    assert "event: sources" in body
    assert "event: done" in body
    assert '"message_id": "m-1"' in body
    # data 应为 JSON（非 Python repr）
    assert '"thread_id": "t1"' in body


def test_chat_validation() -> None:
    """question 为空应 422。"""
    resp = client.post("/v1/chat", json={"question": ""})
    assert resp.status_code == 422
