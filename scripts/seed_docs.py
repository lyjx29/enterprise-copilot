"""摄入课程财报 PDF 到 Qdrant（M1 验证用；M4 升级为正式摄取管线）。

用法：
    python -m scripts.seed_docs --data-dir <课程数据目录>

分块策略（M1 简化版）：按页分块（PageRAG）。M4 升级为层级语义分块（§8.7.2）。
元数据：从文件名解析（amazon 10-k 2024.pdf / amazon 10-q q1 2024.pdf）。
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from pathlib import Path

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, HnswConfigDiff, PointStruct, VectorParams

from app.core.config import get_settings
from app.core.llm import get_embeddings


def extract_pages(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    return [page.extract_text() or "" for page in reader.pages]


def extract_metadata(filename: str) -> dict:
    """从文件名解析元数据：'amazon 10-k 2024.pdf' / 'amazon 10-q q1 2024.pdf'。"""
    parts = filename.replace(".pdf", "").split()
    meta = {"company_name": parts[0], "doc_type": parts[1]}
    if len(parts) == 4:
        meta["fiscal_quarter"] = parts[2]
        meta["fiscal_year"] = int(parts[3])
    else:
        meta["fiscal_quarter"] = None
        meta["fiscal_year"] = int(parts[2])
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="摄入财报 PDF 到 Qdrant")
    parser.add_argument("--data-dir", required=True, help="含 PDF 的课程数据目录")
    args = parser.parse_args()

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    embeddings = get_embeddings(settings)

    # 确认 collection（用样本确定 embedding 维度）
    probe = embeddings.embed_query("probe")
    dim = len(probe)
    client.recreate_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(
            m=settings.qdrant_hnsw_m, ef_construct=settings.qdrant_hnsw_ef_construct
        ),
    )
    print(f"collection '{settings.qdrant_collection}' 已重建 (dim={dim})")

    pdfs = sorted(Path(args.data_dir).glob("**/*.pdf"))
    total_points = 0
    for pdf in pdfs:
        meta = extract_metadata(pdf.name)
        file_hash = hashlib.md5(pdf.read_bytes()).hexdigest()
        pages = extract_pages(pdf)
        points = []
        for page_num, text in enumerate(pages, start=1):
            if len(text.strip()) < 50:  # 跳过空白页
                continue
            vec = embeddings.embed_query(text[:3000])
            payload = {
                **meta,
                "page": page_num,
                "file_hash": file_hash,
                "source_file": pdf.name,
                "content": text[:2000],
            }
            # Qdrant point ID 需为整数或 UUID；用确定性 uuid5（重跑不重复）
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{meta['company_name']}-{meta['doc_type']}-"
                    f"{meta.get('fiscal_year')}-p{page_num}",
                )
            )
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))
        if points:
            client.upsert(collection_name=settings.qdrant_collection, points=points)
            total_points += len(points)
            print(f"  {pdf.name}: {len(points)} pages → 累计 {total_points}")

    print(f"完成：{len(pdfs)} 个 PDF，共 {total_points} 个文档块")


if __name__ == "__main__":
    main()
