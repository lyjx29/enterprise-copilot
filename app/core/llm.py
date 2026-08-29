"""模型工厂：LLM / Embedding 的统一出口（ADR-2）。

- get_llm       生成/推理用（qwen3）
- get_embeddings bi-encoder，召回用（nomic-embed-text）
- get_reranker   cross-encoder，精排用（bge-reranker）——M4 检索流水线引入

原则：全项目只经此工厂取模型，便于切换与测试。
"""
from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.core.config import Settings, get_settings


def get_llm(settings: Settings | None = None) -> BaseChatModel:
    """生成/推理用 LLM。默认本地 Ollama，可切 openai / anthropic。"""
    settings = settings or get_settings()
    kwargs: dict = {"temperature": 0}
    if settings.llm_provider == "ollama":
        return ChatOllama(model=settings.llm_model, base_url=settings.llm_base_url, **kwargs)
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.llm_model, **kwargs)
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.llm_model, **kwargs)
    raise ValueError(f"不支持的 llm_provider: {settings.llm_provider}")


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    """bi-encoder 召回 embedding。默认本地 Ollama。"""
    settings = settings or get_settings()
    if settings.llm_provider == "ollama":
        return OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.llm_base_url,
            num_ctx=settings.embedding_num_ctx,
        )
    if settings.llm_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=settings.embedding_model)
    raise ValueError(f"不支持的 embedding provider: {settings.llm_provider}")
