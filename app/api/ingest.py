"""POST /v1/ingest —— 上传文档并走摄取管线（PROJECT_PLAN §10.3）。"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.services import ingest_service

router = APIRouter(tags=["ingest"])


@router.post("/v1/ingest")
async def ingest(file: UploadFile = File(...)) -> dict:
    """上传 PDF 财报 → 摄取到 Qdrant → {ingested, skipped}。"""
    data = await file.read()
    filename = file.filename or "document.pdf"
    return ingest_service.ingest_pdf(filename, data)
