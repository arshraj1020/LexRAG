"""
Dense (Vector) Retrieval using pgvector.

Uses cosine similarity on normalised embeddings.
Supports optional metadata filtering (court, year, jurisdiction).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.embedder import embed_query
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    citation_id: str
    document_id: str
    page_number: Optional[int]
    paragraph_number: Optional[int]
    section: Optional[str]
    text: str
    case_name: Optional[str]
    court: Optional[str]
    case_year: Optional[str]
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0


async def dense_search(
    db: AsyncSession,
    query: str,
    top_k: int,
    document_ids: Optional[list[str]] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> list[RetrievedChunk]:
    """
    Retrieve top-k chunks by vector cosine similarity.

    Filters are applied at the database level (pre-retrieval filtering)
    for efficiency.
    """
    # embed_query is CPU-bound (PyTorch inference) — run in thread pool to
    # avoid blocking the async event loop during model inference.
    loop = asyncio.get_running_loop()
    query_embedding = await loop.run_in_executor(None, embed_query, query)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Build optional WHERE clauses
    conditions = ["1=1"]
    params: dict = {"embedding": embedding_str, "top_k": top_k}

    if document_ids:
        conditions.append("dc.document_id = ANY(:doc_ids)")
        params["doc_ids"] = document_ids

    if court:
        conditions.append("dc.court ILIKE :court")
        params["court"] = f"%{court}%"

    if year_from:
        # Guard: only cast rows where case_year is a 4-digit numeric string
        # to avoid errors on NULL or non-numeric values stored from OCR.
        conditions.append(
            "dc.case_year ~ '^[0-9]+$' AND CAST(dc.case_year AS INTEGER) >= :year_from"
        )
        params["year_from"] = year_from

    if year_to:
        conditions.append(
            "dc.case_year ~ '^[0-9]+$' AND CAST(dc.case_year AS INTEGER) <= :year_to"
        )
        params["year_to"] = year_to

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            dc.citation_id,
            dc.document_id::text,
            dc.page_number,
            dc.paragraph_number,
            dc.section,
            dc.text,
            dc.case_name,
            dc.court,
            dc.case_year,
            1 - (dc.embedding <=> :embedding::vector) AS score
        FROM document_chunks dc
        WHERE {where_clause}
            AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        RetrievedChunk(
            citation_id=row.citation_id,
            document_id=row.document_id,
            page_number=row.page_number,
            paragraph_number=row.paragraph_number,
            section=row.section,
            text=row.text,
            case_name=row.case_name,
            court=row.court,
            case_year=row.case_year,
            dense_score=float(row.score),
        )
        for row in rows
    ]
