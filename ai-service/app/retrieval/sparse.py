"""
Sparse (Keyword) Retrieval using PostgreSQL full-text search.

Legal research involves exact terminology (Section 438, Article 21,
CrPC, IPC, specific case names) where BM25/FTS outperforms dense retrieval.

Uses PostgreSQL's built-in tsvector/tsquery for zero-dependency keyword search.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .dense import RetrievedChunk

logger = logging.getLogger(__name__)


async def sparse_search(
    db: AsyncSession,
    query: str,
    top_k: int,
    document_ids: Optional[list[str]] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> list[RetrievedChunk]:
    """
    Retrieve top-k chunks by full-text search relevance (ts_rank_cd).

    Legal terms like "Section 438 CrPC" are matched exactly.
    """
    conditions = ["1=1"]
    params: dict = {"query": query, "top_k": top_k}

    if document_ids:
        conditions.append("dc.document_id = ANY(:doc_ids)")
        params["doc_ids"] = document_ids

    if court:
        conditions.append("dc.court ILIKE :court")
        params["court"] = f"%{court}%"

    if year_from:
        # Guard: only cast rows where case_year is a numeric string
        # to avoid errors on NULL or non-numeric values from OCR.
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

    # Use websearch_to_tsquery for natural query parsing
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
            ts_rank_cd(dc.text_search_vector, websearch_to_tsquery('english', :query)) AS score
        FROM document_chunks dc
        WHERE {where_clause}
            AND dc.text_search_vector @@ websearch_to_tsquery('english', :query)
        ORDER BY score DESC
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
            sparse_score=float(row.score),
        )
        for row in rows
    ]
