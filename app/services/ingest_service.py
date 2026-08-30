"""文档摄取服务：上传 PDF → 解析 → 分块 → 向量化 → 入库 Qdrant（PROJECT_PLAN §8.6）。"""

from __future__ import annotations

import hashlib
import io
import uuid

from pypdf import PdfReader
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from app.core.config import get_settings
from app.core.llm import get_embeddings
from app.tools.retrieval import get_qdrant_client


def extract_metadata(filename: str) -> dict:
    """从文件名解析元数据：'amazon 10-k 2024.pdf' / 'amazon 10-q q1 2024.pdf'。"""
    name = filename.replace(".pdf", "")
    parts = name.split()
    if len(parts) < 2:
        return {"company_name": "unknown", "doc_type": "10-k", "fiscal_quarter": None}
    meta = {"company_name": parts[0], "doc_type": parts[1]}
    if len(parts) >= 4 and parts[2].startswith("q"):
        meta["fiscal_quarter"] = parts[2]
        meta["fiscal_year"] = int(parts[3])
    else:
        meta["fiscal_quarter"] = None
        meta["fiscal_year"] = int(parts[-1])
    return meta


def ingest_pdf(filename: str, data: bytes) -> dict:
    """摄取单个 PDF：解析 → 按页分块 → 向量化 → upsert Qdrant（hash 去重）。"""
    settings = get_settings()
    client = get_qdrant_client(settings)
    embeddings = get_embeddings(settings)

    file_hash = hashlib.md5(data).hexdigest()

    # hash 去重
    existing = client.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="file_hash", match=MatchValue(value=file_hash))]
        ),
        limit=1,
    )
    if existing[0]:
        return {"ingested": 0, "skipped": 1}

    # 确保 collection 存在（首次摄取时创建）
    collections = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in collections:
        probe = embeddings.embed_query("probe")
        from qdrant_client.models import Distance, VectorParams

        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=len(probe), distance=Distance.COSINE),
        )

    meta = extract_metadata(filename)
    reader = PdfReader(io.BytesIO(data))
    points = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if len(text.strip()) < 50:
            continue
        vec = embeddings.embed_query(text[:3000])
        payload = {
            **meta,
            "page": page_num,
            "file_hash": file_hash,
            "source_file": filename,
            "content": text[:2000],
        }
        point_id = str(
            uuid.uuid5(uuid.NAMESPACE_DNS, f"{meta['company_name']}-{filename}-p{page_num}")
        )
        points.append(PointStruct(id=point_id, vector=vec, payload=payload))

    if points:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
    return {"ingested": len(points), "skipped": 0}
