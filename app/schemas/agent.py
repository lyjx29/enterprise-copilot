"""Agent 层内部模型：路由判定 + 查询理解 + 来源引用。

RouterQuery 同时承载两件事：
1. Supervisor Router 的 datasource 判定（可评估、可 golden-set 对齐）
2. 查询理解（metadata 过滤 / 查询改写 / 关键词 / HYDE）——RAG 分支消费
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Datasource = Literal["rag", "sql", "web"]


class RouterQuery(BaseModel):
    """Supervisor Router 的结构化输出。"""

    datasource: Datasource = Field(description="该问题应走的数据源路径")
    reason: str = Field(description="判定的简要理由")

    # ---- 查询理解（RAG 分支消费）----
    company: str | None = Field(default=None, description="公司名，如 amazon")
    doc_type: str | None = Field(default=None, description="文档类型，如 10-k / 10-q")
    fiscal_year: int | None = Field(default=None, description="财年，如 2023")
    fiscal_quarter: str | None = Field(default=None, description="财季，如 q1")
    keywords: list[str] = Field(
        default_factory=list, description="3-5 个检索关键词（喂 BM25 稀疏路）"
    )
    rewritten_query: str = Field(
        default="", description="改写后的检索查询（澄清 + 去噪 + 补全）"
    )
    hyde_document: str | None = Field(
        default=None, description="HYDE 假设文档（可选，enable_hyde 时生成）"
    )


class DocSource(BaseModel):
    """单个文档来源引用（RAG 分支输出，供 SSE sources 事件与日志使用）。"""

    company: str | None = None
    doc_type: str | None = None
    fiscal_year: int | None = None
    fiscal_quarter: str | None = None
    page: int | None = None
    score: float | None = None
    content: str | None = None
