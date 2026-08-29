"""Web 搜索工具（DuckDuckGo，兜底路径，PROJECT_PLAN §8.4 / NG6）。"""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """搜索实时信息（DuckDuckGo）。返回标题/摘要/链接列表。

    用于文档库/数据库无法回答的实时或外部信息问题。
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "错误: 缺少 duckduckgo-search 依赖，请运行 uv sync"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        return f"搜索失败: {exc}"

    if not results:
        return "无搜索结果。"

    lines = []
    for r in results:
        title = r.get("title", "")
        href = r.get("href", "")
        body = (r.get("body") or "")[:200]
        lines.append(f"- {title}\n  {href}\n  {body}")
    return "\n".join(lines)
