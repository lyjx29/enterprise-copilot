"""线程与消息的 CRUD（SQLite，自建表，与 LangGraph checkpointer 互补）。

LangGraph checkpointer 管图内部状态；本服务管面向用户的消息记录（含 sources）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings, get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.checkpoint_db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def create_thread(title: str = "") -> str:
    """创建新线程，返回 thread_id。"""
    conn = _connect()
    try:
        thread_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO threads (id, created_at, title) VALUES (?, ?, ?)",
            (thread_id, _now(), title),
        )
        conn.commit()
        return thread_id
    finally:
        conn.close()


def add_message(thread_id: str, role: str, content: str, sources: list[dict] | None = None) -> str:
    """落库一条消息（含 sources JSON），返回 message_id。"""
    conn = _connect()
    try:
        message_id = f"m-{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO messages (id, thread_id, role, content, sources, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                thread_id,
                role,
                content,
                json.dumps(sources or [], ensure_ascii=False),
                _now(),
            ),
        )
        conn.commit()
        return message_id
    finally:
        conn.close()


def list_messages(thread_id: str) -> list[dict]:
    """拉取某线程的历史消息（按时间升序）。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, role, content, sources, created_at FROM messages "
            "WHERE thread_id = ? ORDER BY created_at",
            (thread_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "sources": json.loads(r[3]) if r[3] else [],
                "created_at": r[4],
            }
            for r in rows
        ]
    finally:
        conn.close()
