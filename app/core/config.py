"""应用配置（pydantic-settings）。

所有敏感项只来自环境变量 / .env；本文件不含任何密钥。
字段与 PROJECT_PLAN §8.1 一一对应。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FinCopilot 全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FinCopilot"
    version: str = "0.1.0"

    # ---- LLM（生成/推理）----
    llm_provider: str = "ollama"  # "ollama" | "openai" | "anthropic"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3"

    # ---- Embedding（bi-encoder，召回）----
    embedding_model: str = "nomic-embed-text"
    embedding_num_ctx: int = 8192

    # ---- Reranker（cross-encoder，精排）——本地优先，可切云端 ----
    rerank_provider: str = "ollama"
    rerank_model: str = "bge-reranker"

    # ---- 分块（离线索引）----
    chunk_strategy: str = "semantic_page"  # semantic_page | plain_page | llm_page
    chunk_semantic_threshold: float = 0.2

    # ---- 向量库（Qdrant 独立服务）----
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "financial_docs"
    qdrant_hnsw_m: int = 16
    qdrant_hnsw_ef_construct: int = 100

    # ---- 数据 ----
    employees_db_uri: str = "sqlite:///data/employees.db"  # 只读打开
    checkpoint_db_path: str = "data/checkpoints.db"

    # ---- 检索（双路召回 → 融合 → 精排）----
    enable_hyde: bool = False
    enable_prf: bool = False
    fusion_method: str = "rrf"  # rrf | simple_merge
    recall_top_n1: int = 20  # 稠密路
    recall_top_n2: int = 20  # 稀疏路
    fuse_top_n: int = 15
    rerank_top_k: int = 5
    grade_threshold: float = 0.6  # Self-RAG 门控阈值

    # ---- SQL 安全（纵深防御）----
    sql_allowed_tables: list[str] = Field(
        default_factory=lambda: [
            "employees",
            "departments",
            "dept_emp",
            "salaries",
            "titles",
        ]
    )
    sql_query_timeout_s: float = 3.0
    sql_max_rows: int = 100

    # ---- 安全 ----
    api_keys: list[str] = Field(default_factory=list)  # env API_KEYS=["k1","k2"]
    rate_limit_per_minute: int = 60

    # ---- 观测（Langfuse 可选）----
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # ---- 运行时 ----
    max_iterations: int = 3
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """全局单例配置（FastAPI 依赖注入与全局共享用）。"""
    return Settings()
