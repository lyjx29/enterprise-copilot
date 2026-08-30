"""文档检索工具（企业级混合检索，见 PROJECT_PLAN §8.7）。

M1 骨架：Qdrant 稠密向量检索（带 payload 过滤）。
M4 升级：双路召回（Qdrant dense + BM25 稀疏）→ RRF 融合 → cross-encoder 精排。

设计要点：整条检索流水线封装成单工具，供 RAG Sub-agent 调用，
避免 agent 在低层步骤里迷失（PROJECT_PLAN §8.3）。
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.core.config import Settings, get_settings
from app.core.llm import get_llm


def get_qdrant_client(settings: Settings | None = None):
    """Qdrant 客户端单例（依赖注入用）。"""
    settings = settings or get_settings()
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.qdrant_url)


@tool
def retrieve_docs(
    query: str,
    top_k: int = 5,
    company: str | None = None,
    fiscal_year: int | None = None,
) -> str:
    """从财报文档库检索相关内容（企业级混合检索：双路召回 + RRF 融合）。

    参数：
        query: 检索查询文本
        top_k: 返回文档数（默认 5）
        company: 公司名过滤（如 amazon，忽略大小写）
        fiscal_year: 财年过滤（如 2023）

    返回格式化文档文本（含来源元数据）。向量库未就绪时返回提示。
    """
    settings = get_settings()
    client = get_qdrant_client(settings)

    # 确认 collection 存在（避免 Qdrant 未初始化时报生错）
    try:
        collections = client.get_collections().collections
    except Exception as exc:
        return f"向量库不可用: {exc}（请确认 Qdrant 已启动）"

    if settings.qdrant_collection not in {c.name for c in collections}:
        return (
            f"向量库 '{settings.qdrant_collection}' 尚为空/不存在，"
            "请先摄取财报文档（/v1/ingest 或摄取脚本）。"
        )

    from app.tools.retriever import HybridRetriever

    retriever = HybridRetriever(settings)
    return retriever.retrieve(query, company=company, fiscal_year=fiscal_year, top_k=top_k)


@tool
def rewrite_query(query: str) -> str:
    """改写检索查询以提升命中率（澄清、补全、去噪）。

    保留公司名/财年等关键实体，去掉口语化表述。
    """
    settings = get_settings()
    llm = get_llm(settings)
    prompt = (
        "改写下面的检索查询，使其更可能命中相关财报段落。"
        "保留公司名/财年等关键实体，去掉口语化表述。\n"
        f"原查询: {query}\n改写后:"
    )
    return str(llm.invoke(prompt).content)
