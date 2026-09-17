"""
LexRAG AI Service — Configuration

All values read from environment variables.
No hardcoded secrets or model names.
"""

import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

_logger = logging.getLogger(__name__)

_INSECURE_DEFAULTS = {"changeme_internal_key", "", "change_me", "secret", "changeme"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql://lexrag:changeme@localhost:5432/lexrag"

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Ollama / LLM ──────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "mistral"

    # ── Embeddings ────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Reranker ──────────────────────────────────────────────
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── Retrieval ─────────────────────────────────────────────
    top_k: int = 20
    rerank_top_k: int = 8
    hybrid_dense_weight: float = 0.6
    hybrid_sparse_weight: float = 0.4

    # ── Chunking ──────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_chunk_size: int = 1024

    # ── File Storage ──────────────────────────────────────────
    upload_dir: str = "/app/uploads"

    # ── Security ──────────────────────────────────────────────
    internal_api_key: str = "changeme_internal_key"

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("internal_api_key")
    @classmethod
    def warn_insecure_key(cls, v: str) -> str:
        """
        Warn loudly (but don't crash) when the internal API key is left at
        its default/empty value. An empty key disables authentication entirely
        when both backend and AI service have the same empty value — that is
        a serious misconfiguration.
        """
        if v in _INSECURE_DEFAULTS:
            _logger.warning(
                "SECURITY WARNING: INTERNAL_API_KEY is set to an insecure default ('%s'). "
                "Set a strong random value in your .env file before exposing this service. "
                "Example: openssl rand -hex 32",
                v if v else "<empty>",
            )
        return v

    @property
    def is_development(self) -> bool:
        return self.log_level.upper() == "DEBUG"


@lru_cache
def get_settings() -> Settings:
    return Settings()
