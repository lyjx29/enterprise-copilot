"""企业级混合检索器（PROJECT_PLAN §8.7，阶段一）。

双路召回：Qdrant dense（HNSW + payload filter）+ BM25 稀疏（rank_bm25）
→ RRF 融合 → 可选 cross-encoder 精排（当前环境 reranker 不可用，跳过，OQ-6）。

用法：检索流水线封装成 retrieve_docs 工具，供 RAG Sub-agent 调用（§8.3）。
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rank_bm25 import BM25Okapi

from app.core.config import Settings, get_settings
from app.core.llm import get_embeddings


class HybridRetriever:
    """双路召回 + RRF 融合的混合检索器。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = QdrantClient(url=self.settings.qdrant_url)
        self.embeddings = get_embeddings(self.settings)
        self._corpus: list[dict] | None = None  # [{id, content, payload}]
        self._bm25: BM25Okapi | None = None

    # ---- 语料懒加载（从 Qdrant scroll 全量，供 BM25 稀疏路）----

    def _load_corpus(self) -> None:
        if self._corpus is not None:
            return
        points, offset = [], None
        while True:
            batch, offset = self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            points.extend(batch)
            if offset is None:
                break
        self._corpus = [
            {"id": p.id, "content": (p.payload or {}).get("content", ""), "payload": p.payload}
            for p in points
            if (p.payload or {}).get("content")
        ]
        tokenized = [doc["content"].split() for doc in self._corpus]
        self._bm25 = BM25Okapi(tokenized)

    # ---- 双路召回 ----

    def _dense_recall(self, query: str, filters: dict, top_n: int) -> list[tuple[str, float]]:
        vec = self.embeddings.embed_query(query)
        conditions = []
        for key, value in filters.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        query_filter = Filter(must=conditions) if conditions else None
        hits = self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=vec,
            limit=top_n,
            query_filter=query_filter,
        ).points
        return [(h.id, h.score or 0.0) for h in hits]

    def _sparse_recall(self, query: str, filters: dict, top_n: int) -> list[tuple[str, float]]:
        """BM25 稀疏召回（支持 metadata filter，与稠密路对齐）。"""
        self._load_corpus()
        scores = self._bm25.get_scores(query.split())
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])
        results: list[tuple[str, float]] = []
        for i, s in ranked:
            doc = self._corpus[i]
            payload = doc["payload"] or {}
            if all(payload.get(k) == v for k, v in filters.items()):
                results.append((doc["id"], float(s)))
                if len(results) >= top_n:
                    break
        return results

    # ---- RRF 融合 ----

    @staticmethod
    def _rrf(ranked_lists: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank, (doc_id, _score) in enumerate(ranked):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: -x[1])

    # ---- LLM-as-reranker（环境无 cross-encoder 模型的精排替代）----

    def _llm_rerank(self, query: str, candidates: list[dict]) -> list[tuple[str, float]]:
        """用生成模型对候选文档打分（0-10），按分数排序返回 [(doc_id, score)]。

        失败时降级为原顺序（不阻断检索链路）。
        """
        from langchain_core.prompts import ChatPromptTemplate
        from pydantic import BaseModel

        from app.core.llm import get_llm

        class RerankScore(BaseModel):
            index: int
            score: float

        class RerankResult(BaseModel):
            scores: list[RerankScore]

        docs_text = "\n\n".join(f"[{i}] {doc['content'][:400]}" for i, doc in enumerate(candidates))
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是检索相关性评分器。根据查询判断每个候选文档的相关性，每项打分 0-10（10=完全相关）。"
                    "只输出 JSON，scores 为数组，每项含 index 和 score。",
                ),
                ("human", "查询: {query}\n\n候选文档:\n{docs}"),
            ]
        )
        llm = get_llm(self.settings)
        try:
            result = (prompt | llm.with_structured_output(RerankResult)).invoke(
                {"query": query, "docs": docs_text}
            )
            score_map = {s.index: s.score for s in result.scores}
            ranked_idx = sorted(
                range(len(candidates)), key=lambda i: score_map.get(i, 0), reverse=True
            )
            return [(candidates[i]["id"], score_map.get(i, 0.0)) for i in ranked_idx]
        except Exception:
            # 降级：按候选原顺序（RRF 序）
            return [(d["id"], 0.0) for d in candidates]

    # ---- 主入口 ----

    def retrieve(
        self,
        query: str,
        company: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 5,
    ) -> str:
        """混合检索：双路召回 → RRF 融合 →（可选 LLM 精排）→ 返回格式化文档文本。"""
        s = self.settings
        filters: dict = {}
        if company:
            filters["company_name"] = company.lower()
        if fiscal_year is not None:
            filters["fiscal_year"] = fiscal_year

        dense = self._dense_recall(query, filters, s.recall_top_n1)
        sparse = self._sparse_recall(query, filters, s.recall_top_n2)
        fused = self._rrf([dense, sparse])[: s.fuse_top_n]

        doc_map = {d["id"]: d for d in (self._corpus or [])}
        selected: list[tuple[str, float]] = fused[:top_k]

        # LLM-as-reranker 精排（默认开启）
        if s.rerank_enabled:
            candidates = [doc_map[doc_id] for doc_id, _ in fused if doc_id in doc_map]
            if candidates:
                ranked = self._llm_rerank(query, candidates)
                selected = ranked[:top_k]

        lines = []
        for doc_id, score in selected:
            doc = doc_map.get(doc_id)
            if doc is None:
                continue
            payload = doc["payload"] or {}
            meta = {
                "company": payload.get("company_name", "?"),
                "doc_type": payload.get("doc_type", "?"),
                "year": payload.get("fiscal_year", "?"),
                "quarter": payload.get("fiscal_quarter", "?"),
                "page": payload.get("page", "?"),
            }
            lines.append(
                f"[score={round(score, 3)} | {meta['company']} {meta['doc_type']} "
                f"{meta['year']} {meta['quarter']} p.{meta['page']}]\n{doc['content'][:600]}"
            )
        return "\n\n---\n\n".join(lines) if lines else "未检索到相关文档。"
