"""
LexRAG AI Service — FastAPI Application Entry Point
"""

import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.core.settings import get_settings

settings = get_settings()

# ── Structured logging ────────────────────────────────────────
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    )
)
logger = structlog.get_logger()


# ── Lifespan (replaces deprecated @app.on_event) ─────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown logic."""
    logger.info("LexRAG AI Service starting", model=settings.llm_model)
    yield
    logger.info("LexRAG AI Service shutting down")


# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title="LexRAG AI Service",
    description=(
        "Internal AI service for LexRAG Legal Research Platform. "
        "Handles document ingestion, retrieval, reranking, and LLM generation. "
        "All endpoints require X-Internal-Api-Key header. "
        "NOT intended for direct public access."
    ),
    version="0.1.0",
    docs_url="/docs",   # disable in production: docs_url=None
    redoc_url=None,
    lifespan=lifespan,
)

# ── Prometheus metrics ────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics")

# ── Middleware ────────────────────────────────────────────────
# Internal service — no public CORS needed.
# Only allow calls from the backend container.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://backend:8080"],
    allow_methods=["POST", "GET"],
    allow_headers=["X-Internal-Api-Key"],
)

# ── Routes ────────────────────────────────────────────────────
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    """Public health endpoint for Docker health check."""
    return {"status": "ok", "service": "lexrag-ai-service"}
