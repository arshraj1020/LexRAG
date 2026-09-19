"""
LexRAG AI Service — Internal API Routes (v1)

These endpoints are called ONLY by the Spring Boot backend.
All routes require the X-Internal-Api-Key header.
They are NOT exposed to the public internet.

SECURITY:
- file_path is validated to be within the configured upload directory
  (path traversal protection — the AI service never blindly trusts the path)
- Retrieved documents are treated as UNTRUSTED DATA (prompt injection defense)
- Debug/trace mode is disabled by default; requires explicit opt-in via request flag
  and LOG_LEVEL=DEBUG (never available in production)
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from ..core.database import get_db
from ..core.dependencies import verify_internal_api_key
from ..core.settings import get_settings
from ..ingestion.pipeline import ingest_document
from ..retrieval.dense import dense_search
from ..retrieval.hybrid import hybrid_search
from ..retrieval.reranker import rerank
from ..generation.ollama import OllamaProvider
from ..generation.prompts.legal_research_prompt import build_research_prompt
from ..generation.prompts.comparison_prompt import (
    COMPARISON_SYSTEM_PROMPT, build_comparison_prompt,
)
from ..generation.prompts.precedent_prompt import (
    PRECEDENT_SYSTEM_PROMPT, build_precedent_prompt,
)
from ..generation.prompts.provision_prompt import (
    PROVISION_SYSTEM_PROMPT, build_provision_prompt,
)
from ..generation.prompts.brief_prompt import (
    BRIEF_SYSTEM_PROMPT, build_brief_prompt,
)
from ..citations.citation_verifier import verify_citations
from ..retrieval.query_expander import expand_query

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/internal", dependencies=[Depends(verify_internal_api_key)])

_llm = OllamaProvider()

# Canonical upload directory (resolved once at startup)
_UPLOAD_DIR = Path(settings.upload_dir).resolve()

# Confidence string → float mapping (LLM returns strings; Java backend expects float)
_CONFIDENCE_MAP = {"HIGH": 0.85, "MEDIUM": 0.55, "LOW": 0.25}


# ── Request / Response models ──────────────────────────────────

class IngestRequest(BaseModel):
    document_id: str
    file_path: str


class SearchRequest(BaseModel):
    query: str
    document_ids: Optional[list[str]] = None
    strategy: str = Field(default="HYBRID", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    top_k: int = Field(default=None, ge=1, le=100)
    rerank_top_k: int = Field(default=None, ge=1, le=50)
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None


class GenerateRequest(BaseModel):
    question: str
    document_ids: Optional[list[str]] = None
    strategy: str = Field(default="HYBRID_RERANK", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    # debug mode: true only honoured when LOG_LEVEL=DEBUG; never exposed in production
    debug: bool = False


class CompareRequest(BaseModel):
    question: str
    document_ids: list[str] = Field(min_length=2, max_length=10)
    strategy: str = Field(default="HYBRID_RERANK", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None


class PrecedentRequest(BaseModel):
    query: str
    document_ids: Optional[list[str]] = None
    strategy: str = Field(default="HYBRID_RERANK", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    court: Optional[str] = None
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=25)


class ProvisionRequest(BaseModel):
    # Accept both 'provision' (from Spring Boot) and 'provision_query' (legacy)
    provision: Optional[str] = None
    provision_query: Optional[str] = None
    document_ids: Optional[list[str]] = None
    strategy: str = Field(default="HYBRID_RERANK", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None

    @property
    def effective_provision(self) -> str:
        """Returns the provision text from whichever field was set."""
        return self.provision or self.provision_query or ""


class BriefRequest(BaseModel):
    research_question: str
    document_ids: Optional[list[str]] = None
    strategy: str = Field(default="HYBRID_RERANK", pattern="^(DENSE|HYBRID|HYBRID_RERANK)$")
    court: Optional[str] = None
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    document_type: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────

@router.post("/ingest")
async def ingest(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a document: extract → chunk → embed → store in pgvector.
    Long-running — returns immediately and processes in background.
    Spring Boot tracks status via document.status field.

    SECURITY: file_path is validated to be within the upload directory
    before any file access occurs. Path traversal is rejected with 400.
    """
    validated_path = _validate_file_path(request.file_path)
    background_tasks.add_task(_run_ingestion, request.document_id, str(validated_path))
    return {"status": "PROCESSING", "document_id": request.document_id}


@router.post("/search")
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve relevant chunks using the specified strategy."""
    top_k = request.top_k or settings.top_k
    rerank_top_k = request.rerank_top_k or settings.rerank_top_k
    kwargs = dict(
        db=db,
        query=request.query,
        top_k=top_k,
        document_ids=request.document_ids,
        court=request.court,
        year_from=request.year_from,
        year_to=request.year_to,
    )

    if request.strategy == "DENSE":
        chunks = await dense_search(**kwargs)
    else:
        chunks = await hybrid_search(**kwargs)
        if request.strategy == "HYBRID_RERANK":
            # rerank() is CPU-bound (cross-encoder inference) — run in thread pool
            loop = asyncio.get_running_loop()
            chunks = await loop.run_in_executor(None, rerank, request.query, chunks, rerank_top_k)

    return {"chunks": [_chunk_to_dict(c) for c in chunks], "strategy": request.strategy}


@router.post("/generate")
async def generate(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Full RAG pipeline: retrieval → (optional query expansion) → reranking → LLM → citation verification.

    The debug flag is honoured ONLY when the service is running in development mode
    (LOG_LEVEL=DEBUG). In production, the trace section is always omitted so internal
    file paths, model scores, and prompt contents are never returned to callers.
    """
    rerank_top_k = settings.rerank_top_k
    include_trace = request.debug and settings.is_development

    # ── Step 1: Query expansion (multi-query) ─────────────────
    # Expand the question to multiple sub-queries to improve recall.
    # Falls back to [question] if expansion fails — never blocks retrieval.
    expanded_queries = expand_query(request.question)

    # ── Step 2: Retrieval ─────────────────────────────────────
    all_chunks = []
    seen_ids: set[str] = set()

    for q in expanded_queries:
        if request.strategy == "DENSE":
            candidates = await dense_search(
                db=db, query=q, top_k=settings.top_k,
                document_ids=request.document_ids,
                court=request.court, year_from=request.year_from, year_to=request.year_to,
            )
        else:
            candidates = await hybrid_search(
                db=db, query=q, top_k=settings.top_k,
                document_ids=request.document_ids,
                court=request.court, year_from=request.year_from, year_to=request.year_to,
            )
        for c in candidates:
            if c.citation_id not in seen_ids:
                all_chunks.append(c)
                seen_ids.add(c.citation_id)

    # ── Step 3: Reranking ─────────────────────────────────────
    # rerank() is CPU-bound (cross-encoder inference) — offload to thread pool
    # to avoid blocking the async event loop during model inference.
    if request.strategy == "HYBRID_RERANK" and all_chunks:
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(None, rerank, request.question, all_chunks, rerank_top_k)
    else:
        chunks = all_chunks[:rerank_top_k]

    if not chunks:
        return {
            "answer": "INSUFFICIENT_EVIDENCE",
            "explanation": "No relevant documents found for your query.",
            "citations": [],
            "verified_citations": [],
            "confidence": None,
            "retrieved_chunks": 0,
            "strategy": request.strategy,
        }

    # ── Step 4: LLM generation ────────────────────────────────
    # _llm.generate() is a synchronous HTTP call to Ollama — offload to thread
    # pool to avoid blocking the event loop during LLM inference.
    evidence_blocks = [_chunk_to_dict(c) for c in chunks]
    prompt = build_research_prompt(request.question, evidence_blocks)
    loop = asyncio.get_running_loop()
    llm_response = await loop.run_in_executor(None, _llm.generate, prompt)

    # ── Step 5: Citation verification (citation-first) ────────
    # Pass the set of retrieved citation IDs so the verifier can reject
    # any citation the LLM invented that was never actually retrieved.
    retrieved_ids = {c.citation_id for c in chunks}
    owner_doc_ids = request.document_ids  # may be None (all user docs)
    verified = await verify_citations(
        db,
        llm_response.citations,
        owner_document_ids=owner_doc_ids,
        retrieved_citation_ids=retrieved_ids,
    )

    # Convert confidence string → float (Java backend expects Double)
    confidence_float: Optional[float] = _confidence_to_float(llm_response.confidence)

    response: dict = {
        "answer": llm_response.answer,
        "citations": llm_response.citations,
        "verified_citations": [
            {
                "citation_id": v.citation_id,
                "claim": v.claim,
                "page": v.page,
                "paragraph": v.paragraph,
                "case_name": v.case_name,
                "court": v.court,
                "is_valid": v.is_valid,
                "validation_errors": v.validation_errors,
                "chunk_text": v.chunk_text,
            }
            for v in verified
        ],
        "confidence": confidence_float,
        "retrieved_chunks": len(chunks),
        "strategy": request.strategy,
    }

    # ── Debug/trace (development only) ────────────────────────
    # SECURITY: never exposes file paths, JWT, API keys, or secrets.
    # Only available when explicitly requested AND service is in debug mode.
    if include_trace:
        response["_trace"] = {
            "expanded_queries": expanded_queries,
            "retrieved_count": len(all_chunks),
            "reranked_count": len(chunks),
            "top_chunk_scores": [
                {
                    "citation_id": c.citation_id,
                    "dense_score": round(c.dense_score, 4),
                    "sparse_score": round(c.sparse_score, 4),
                    "fusion_score": round(c.fusion_score, 4),
                    "rerank_score": round(c.rerank_score, 4),
                }
                for c in chunks[:5]
            ],
            "llm_parse_error": llm_response.parse_error,
        }

    return response


@router.post("/compare")
async def compare_cases(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two or more legal cases using hybrid retrieval per document.

    Retrieves evidence from each specified document separately, then generates
    a structured comparison grounded in verified citations.
    """
    rerank_top_k = settings.rerank_top_k
    loop = asyncio.get_running_loop()
    evidence_by_doc: dict[str, list[dict]] = {}
    all_chunks = []

    # Retrieve evidence for each document independently, applying optional metadata filters
    per_doc_rerank_k = max(2, rerank_top_k // len(request.document_ids))
    for doc_id in request.document_ids:
        doc_chunks = await hybrid_search(
            db=db,
            query=request.question,
            top_k=settings.top_k,
            document_ids=[doc_id],
            court=request.court,
            year_from=request.year_from,
            year_to=request.year_to,
        )
        if request.strategy == "HYBRID_RERANK" and doc_chunks:
            doc_chunks = await loop.run_in_executor(
                None, rerank, request.question, doc_chunks, per_doc_rerank_k
            )
        all_chunks.extend(doc_chunks)
        evidence_by_doc[doc_id] = [_chunk_to_dict(c) for c in doc_chunks]

    if not all_chunks:
        return {
            "structured_comparison": None,
            "error": "INSUFFICIENT_EVIDENCE",
            "explanation": "No relevant evidence found in the specified documents.",
            "verified_citations": [],
            "invalid_citations": [],
        }

    # Build prompt with per-document evidence groups
    prompt = build_comparison_prompt(request.question, evidence_by_doc)

    # Generate comparison via LLM with the dedicated comparison system prompt
    llm_response = await loop.run_in_executor(
        None, _llm.generate_with_system, COMPARISON_SYSTEM_PROMPT, prompt
    )

    # Verify citations — must belong to the requested documents and be retrieved
    retrieved_ids = {c.citation_id for c in all_chunks}
    all_verified = await verify_citations(
        db,
        _extract_all_citation_ids(llm_response.raw_text),
        owner_document_ids=request.document_ids,
        retrieved_citation_ids=retrieved_ids,
    )
    valid_citations = [_verified_to_dict(v) for v in all_verified if v.is_valid]
    invalid_citations = [_verified_to_dict(v) for v in all_verified if not v.is_valid]

    return {
        "question": request.question,
        "document_ids": request.document_ids,
        "structured_comparison": llm_response.answer if llm_response.answer != "GENERATION_ERROR" else None,
        "verified_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "retrieved_chunks": len(all_chunks),
        "confidence": llm_response.confidence,
        "strategy": request.strategy,
        "parse_error": llm_response.parse_error,
    }


@router.post("/precedents")
async def find_precedents(
    request: PrecedentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Find relevant precedents using hybrid retrieval + reranking.

    Returns structured precedent results with verified citations.
    """
    top_k = request.top_k or settings.top_k
    rerank_top_k = settings.rerank_top_k
    loop = asyncio.get_running_loop()

    # Expand query for better recall
    expanded_queries = expand_query(request.query)
    all_chunks = []
    seen_ids: set[str] = set()

    for q in expanded_queries:
        candidates = await hybrid_search(
            db=db,
            query=q,
            top_k=top_k,
            document_ids=request.document_ids,
            court=request.court,
            year_from=request.year_from,
            year_to=request.year_to,
        )
        for c in candidates:
            if c.citation_id not in seen_ids:
                all_chunks.append(c)
                seen_ids.add(c.citation_id)

    if request.strategy == "HYBRID_RERANK" and all_chunks:
        all_chunks = await loop.run_in_executor(
            None, rerank, request.query, all_chunks, rerank_top_k
        )

    if not all_chunks:
        return {
            "query": request.query,
            "precedents": [],
            "verified_citations": [],
            "invalid_citations": [],
            "retrieved_chunks": 0,
            "explanation": "No relevant precedents found.",
        }

    evidence = [_chunk_to_dict(c) for c in all_chunks]
    prompt = build_precedent_prompt(request.query, evidence)
    llm_response = await loop.run_in_executor(
        None, _llm.generate_with_system, PRECEDENT_SYSTEM_PROMPT, prompt
    )

    retrieved_ids = {c.citation_id for c in all_chunks}
    all_verified = await verify_citations(
        db,
        _extract_all_citation_ids(llm_response.raw_text),
        owner_document_ids=request.document_ids,
        retrieved_citation_ids=retrieved_ids,
    )
    valid_citations = [_verified_to_dict(v) for v in all_verified if v.is_valid]
    invalid_citations = [_verified_to_dict(v) for v in all_verified if not v.is_valid]

    # Extract the structured precedents list from the LLM JSON response
    precedents_list = []
    try:
        parsed = json.loads(llm_response.answer) if llm_response.answer not in ("GENERATION_ERROR", "") else {}
        if isinstance(parsed, dict):
            precedents_list = parsed.get("precedents", [])
    except (json.JSONDecodeError, Exception):
        pass

    return {
        "query": request.query,
        "precedents": precedents_list,
        "verified_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "retrieved_chunks": len(all_chunks),
        "confidence": llm_response.confidence,
        "strategy": request.strategy,
        "parse_error": llm_response.parse_error,
    }


@router.post("/provision")
async def analyse_provision(
    request: ProvisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse a legal provision/section using retrieved case evidence.

    Retrieves cases discussing the provision and generates a structured
    interpretation analysis. Does not present output as authoritative law.
    """
    provision_text = request.effective_provision
    if not provision_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'provision' or 'provision_query' must be provided",
        )

    loop = asyncio.get_running_loop()
    expanded_queries = expand_query(provision_text)
    all_chunks = []
    seen_ids: set[str] = set()

    for q in expanded_queries:
        candidates = await hybrid_search(
            db=db,
            query=q,
            top_k=settings.top_k,
            document_ids=request.document_ids,
            court=request.court,
            year_from=request.year_from,
            year_to=request.year_to,
        )
        for c in candidates:
            if c.citation_id not in seen_ids:
                all_chunks.append(c)
                seen_ids.add(c.citation_id)

    if request.strategy == "HYBRID_RERANK" and all_chunks:
        all_chunks = await loop.run_in_executor(
            None, rerank, provision_text, all_chunks, settings.rerank_top_k
        )

    if not all_chunks:
        return {
            "provision": provision_text,
            "structured_analysis": None,
            "verified_citations": [],
            "invalid_citations": [],
            "explanation": "INSUFFICIENT_EVIDENCE — no relevant cases found for this provision.",
        }

    evidence = [_chunk_to_dict(c) for c in all_chunks]
    prompt = build_provision_prompt(provision_text, evidence)
    llm_response = await loop.run_in_executor(
        None, _llm.generate_with_system, PROVISION_SYSTEM_PROMPT, prompt
    )

    retrieved_ids = {c.citation_id for c in all_chunks}
    all_verified = await verify_citations(
        db,
        _extract_all_citation_ids(llm_response.raw_text),
        owner_document_ids=request.document_ids,
        retrieved_citation_ids=retrieved_ids,
    )
    valid_citations = [_verified_to_dict(v) for v in all_verified if v.is_valid]
    invalid_citations = [_verified_to_dict(v) for v in all_verified if not v.is_valid]

    return {
        "provision": provision_text,
        "structured_analysis": llm_response.answer if llm_response.answer != "GENERATION_ERROR" else None,
        "verified_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "retrieved_chunks": len(all_chunks),
        "confidence": llm_response.confidence,
        "strategy": request.strategy,
        "disclaimer": "This analysis is for research purposes only and does not constitute legal advice.",
        "parse_error": llm_response.parse_error,
    }


@router.post("/brief")
async def generate_brief(
    request: BriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a structured legal research brief.

    Retrieves evidence, reranks it, and generates a full research brief
    with findings, authorities, arguments, and open questions — all grounded
    in verified citations.
    """
    loop = asyncio.get_running_loop()
    expanded_queries = expand_query(request.research_question)
    all_chunks = []
    seen_ids: set[str] = set()

    for q in expanded_queries:
        candidates = await hybrid_search(
            db=db,
            query=q,
            top_k=settings.top_k,
            document_ids=request.document_ids,
            court=request.court,
            year_from=request.year_from,
            year_to=request.year_to,
        )
        for c in candidates:
            if c.citation_id not in seen_ids:
                all_chunks.append(c)
                seen_ids.add(c.citation_id)

    if request.strategy == "HYBRID_RERANK" and all_chunks:
        # Use a larger context for briefs — more evidence = richer brief
        brief_top_k = min(len(all_chunks), settings.rerank_top_k * 2)
        all_chunks = await loop.run_in_executor(
            None, rerank, request.research_question, all_chunks, brief_top_k
        )

    if not all_chunks:
        return {
            "research_question": request.research_question,
            "structured_brief": None,
            "verified_citations": [],
            "invalid_citations": [],
            "retrieved_chunks": 0,
            "explanation": "INSUFFICIENT_EVIDENCE — no relevant documents found.",
        }

    evidence = [_chunk_to_dict(c) for c in all_chunks]
    prompt = build_brief_prompt(request.research_question, evidence)
    llm_response = await loop.run_in_executor(
        None, _llm.generate_with_system, BRIEF_SYSTEM_PROMPT, prompt
    )

    retrieved_ids = {c.citation_id for c in all_chunks}
    all_verified = await verify_citations(
        db,
        _extract_all_citation_ids(llm_response.raw_text),
        owner_document_ids=request.document_ids,
        retrieved_citation_ids=retrieved_ids,
    )
    valid_citations = [_verified_to_dict(v) for v in all_verified if v.is_valid]
    invalid_citations = [_verified_to_dict(v) for v in all_verified if not v.is_valid]

    return {
        "research_question": request.research_question,
        "structured_brief": llm_response.answer if llm_response.answer != "GENERATION_ERROR" else None,
        "verified_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "retrieved_chunks": len(all_chunks),
        "confidence": llm_response.confidence,
        "strategy": request.strategy,
        "parse_error": llm_response.parse_error,
    }


@router.post("/eval/run")
async def run_evaluation(
    db: AsyncSession = Depends(get_db),
):
    """
    Run the pipeline comparison evaluation experiment.

    Evaluates four configurations (Dense / Hybrid / Hybrid+Rerank / Full Pipeline)
    against the benchmark dataset defined in pipeline_experiment.py.

    IMPORTANT:
    - The experiment requires BENCHMARK_QUERIES to be populated with labelled data.
    - If no labelled queries exist, the experiment is clearly marked BLOCKED.
    - Results are NEVER fabricated — all metrics come from real retrieval calls.
    - Latency figures are wall-clock measurements from actual retrieval.

    Returns a full JSON report with Recall@K, Precision@K, MRR, NDCG@K, MAP,
    and latency statistics (mean, p50, p95) for each pipeline.
    """
    from ...evaluation.pipeline_experiment import run_experiment

    try:
        report = await run_experiment(database_url=settings.database_url)
        return report.to_dict()
    except Exception as exc:
        logger.error("Evaluation experiment failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {exc}",
        )


@router.get("/health")
async def ai_service_health(db: AsyncSession = Depends(get_db)):
    """Internal health check with component status."""
    ollama_ok = _llm.check_availability()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "components": {
            "ollama": "ok" if ollama_ok else "unavailable",
            "model": settings.llm_model,
        },
    }


# ── Security helpers ──────────────────────────────────────────

def _validate_file_path(file_path: str) -> Path:
    """
    Resolve the path and verify it is inside the configured upload directory.

    Rejects:
      - Absolute paths outside upload_dir (e.g. /etc/passwd)
      - Relative paths with '..' that escape the directory
      - Symlinks that resolve outside the directory
      - Non-existent files

    Raises HTTP 400 if validation fails.
    """
    try:
        resolved = Path(file_path).resolve()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid file path") from exc

    # Check containment — resolved path must start with the upload dir
    try:
        resolved.relative_to(_UPLOAD_DIR)
    except ValueError:
        logger.warning(
            "Rejected ingest path outside upload dir: %s (upload_dir=%s)",
            resolved, _UPLOAD_DIR,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File path is not within the permitted upload directory",
        )

    if not resolved.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not exist",
        )

    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path does not refer to a regular file",
        )

    return resolved


def _confidence_to_float(confidence_str: Optional[str]) -> Optional[float]:
    """
    Convert LLM confidence string to a float score for Java/frontend consumption.

    HIGH → 0.85, MEDIUM → 0.55, LOW → 0.25, unknown/None → None
    """
    if confidence_str is None:
        return None
    return _CONFIDENCE_MAP.get(str(confidence_str).upper())


# ── Data helpers ──────────────────────────────────────────────

def _chunk_to_dict(chunk) -> dict:
    return {
        "citation_id": chunk.citation_id,
        "document_id": chunk.document_id,
        "page_number": chunk.page_number,
        "paragraph_number": chunk.paragraph_number,
        "section": chunk.section,
        "text": chunk.text,
        "case_name": chunk.case_name,
        "court": chunk.court,
        "case_year": chunk.case_year,
        "dense_score": chunk.dense_score,
        "sparse_score": chunk.sparse_score,
        "fusion_score": chunk.fusion_score,
        "rerank_score": chunk.rerank_score,
    }


def _verified_to_dict(v) -> dict:
    return {
        "citation_id": v.citation_id,
        "claim": v.claim,
        "page": v.page,
        "paragraph": v.paragraph,
        "case_name": v.case_name,
        "court": v.court,
        "is_valid": v.is_valid,
        "validation_errors": v.validation_errors,
        "chunk_text": v.chunk_text,
    }


def _extract_all_citation_ids(raw_llm_text: str) -> list[dict]:
    """
    Extract citation_id strings from raw LLM JSON text and return them as
    minimal citation dicts for verification. Used when the LLM embeds citation
    IDs in a nested structure (comparison, brief, precedent) rather than a
    flat `citations` array.
    """
    # Try parsing as JSON first
    try:
        cleaned = raw_llm_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        data = json.loads(cleaned)
        ids = _collect_citation_ids_recursive(data)
        return [{"citation_id": cid, "claim": "", "page": None, "paragraph": None}
                for cid in ids]
    except (json.JSONDecodeError, Exception):
        pass

    # Fallback: regex extraction of DOC_... pattern citation IDs
    pattern = r'\bDOC_[A-F0-9]{8}_P\d+_PAR\d+\b'
    found = list(dict.fromkeys(re.findall(pattern, raw_llm_text)))
    return [{"citation_id": cid, "claim": "", "page": None, "paragraph": None}
            for cid in found]


def _collect_citation_ids_recursive(data, seen: set = None) -> list[str]:
    """Recursively collect all citation_id values from a nested JSON structure."""
    if seen is None:
        seen = set()
    ids = []
    if isinstance(data, dict):
        if "citation_id" in data and isinstance(data["citation_id"], str):
            cid = data["citation_id"]
            if cid and cid not in seen:
                ids.append(cid)
                seen.add(cid)
        for key, val in data.items():
            if key in ("citations", "key_citations") and isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item not in seen:
                        ids.append(item)
                        seen.add(item)
            else:
                ids.extend(_collect_citation_ids_recursive(val, seen))
    elif isinstance(data, list):
        for item in data:
            ids.extend(_collect_citation_ids_recursive(item, seen))
    return ids


async def _run_ingestion(document_id: str, file_path: str):
    """Background task — runs ingestion outside request context."""
    from ..core.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await ingest_document(db, document_id, file_path)
        if not result.success:
            # Mark document as FAILED in the database
            await db.execute(text("""
                UPDATE documents
                SET status = 'FAILED', error_message = :error, updated_at = NOW()
                WHERE id = :id::uuid
            """), {"error": result.error, "id": document_id})
            await db.commit()
