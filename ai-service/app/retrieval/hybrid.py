"""
Hybrid Retrieval — Dense + Sparse with Reciprocal Rank Fusion (RRF).

RRF is parameter-free and robust across different retrieval configurations.
Configurable alpha weight for dense/sparse balance.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .dense import RetrievedChunk, dense_search
from .sparse import sparse_search
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# RRF constant — 60 is standard; higher values favour documents ranked low in one list
RRF_K = 60


async def hybrid_search(
    db: AsyncSession,
    query: str,
    top_k: int,
    document_ids: Optional[list[str]] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    dense_weight: Optional[float] = None,
    sparse_weight: Optional[float] = None,
) -> list[RetrievedChunk]:
    """
    Combine dense and sparse retrieval via Reciprocal Rank Fusion.

    Returns top_k chunks ranked by combined RRF score.
    """
    dw = dense_weight if dense_weight is not None else settings.hybrid_dense_weight
    sw = sparse_weight if sparse_weight is not None else settings.hybrid_sparse_weight

    # Fetch more candidates than needed so fusion has material to work with
    fetch_k = min(top_k * 3, 100)

    dense_results, sparse_results = await _fetch_both(
        db, query, fetch_k, document_ids, court, year_from, year_to
    )

    # Build citation→chunk map (dense results take priority for text content)
    chunk_map: dict[str, RetrievedChunk] = {}
    for chunk in dense_results:
        chunk_map[chunk.citation_id] = chunk
    for chunk in sparse_results:
        if chunk.citation_id not in chunk_map:
            chunk_map[chunk.citation_id] = chunk
        else:
            chunk_map[chunk.citation_id].sparse_score = chunk.sparse_score

    # Compute RRF scores
    dense_ranks = {c.citation_id: rank + 1 for rank, c in enumerate(dense_results)}
    sparse_ranks = {c.citation_id: rank + 1 for rank, c in enumerate(sparse_results)}

    all_ids = set(dense_ranks) | set(sparse_ranks)
    for cid in all_ids:
        dr = dense_ranks.get(cid, len(dense_results) + 1)
        sr = sparse_ranks.get(cid, len(sparse_results) + 1)
        rrf = dw * (1.0 / (RRF_K + dr)) + sw * (1.0 / (RRF_K + sr))
        if cid in chunk_map:
            chunk_map[cid].fusion_score = rrf

    sorted_chunks = sorted(chunk_map.values(), key=lambda c: c.fusion_score, reverse=True)
    return sorted_chunks[:top_k]


async def _fetch_both(
    db: AsyncSession,
    query: str,
    fetch_k: int,
    document_ids: Optional[list[str]],
    court: Optional[str],
    year_from: Optional[int],
    year_to: Optional[int],
) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
    """
    Run dense and sparse retrieval sequentially on the same session.

    NOTE: SQLAlchemy AsyncSession is NOT safe for concurrent use — running
    both retrievals via asyncio.gather on the same session causes undefined
    behaviour. Sequential execution is the correct approach here; the
    performance bottleneck is LLM generation, not retrieval.
    """
    dense_results = await dense_search(db, query, fetch_k, document_ids, court, year_from, year_to)
    sparse_results = await sparse_search(db, query, fetch_k, document_ids, court, year_from, year_to)
    return dense_results, sparse_results
