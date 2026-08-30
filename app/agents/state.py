"""LangGraph AgentState（PROJECT_PLAN §8.3）。

messages 用 operator.add reducer 实现追加式更新。
其余字段为各分支节点的输出，供生成/落库/日志使用。
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    datasource: str  # Supervisor Router 判定：rag | sql | web
    query_analysis: dict  # 查询理解（RouterQuery 序列化）
    retrieved_docs: str
    sql_result: str
    web_results: str
    sources: list[dict]
    iteration_count: int
