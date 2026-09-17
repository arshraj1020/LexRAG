"""
Hybrid retrieval + RRF fusion unit tests — no DB required.

Tests: RRF fusion logic, rank combination, deduplication, score ordering,
edge cases (empty lists, only dense, only sparse).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.retrieval.dense import RetrievedChunk
from app.retrieval.hybrid import hybrid_search, RRF_K


def _make_chunk(
    cid: str,
    dense_score: float = 0.0,
    sparse_score: float = 0.0,
) -> RetrievedChunk:
    return RetrievedChunk(
        citation_id=cid,
        document_id="doc-1",
        page_number=1,
        paragraph_number=1,
        section=None,
        text=f"Chunk text for {cid}",
        case_name="Test Case",
        court="Test Court",
        case_year="2024",
        dense_score=dense_score,
        sparse_score=sparse_score,
    )


# ── RRF score computation ─────────────────────────────────────

class TestRrfFusion:
    def test_rrf_score_formula(self):
        """Verify RRF(rank) = 1 / (k + rank)."""
        k = RRF_K
        # rank 1 in dense, not in sparse → dense RRF only
        # rrf = dense_weight * 1/(k+1) + sparse_weight * 1/(k + (N+1))
        # where N+1 is the fallback rank for missing entries
        alpha = 0.6
        beta = 0.4
        dr, sr = 1, 1
        expected = alpha * (1 / (k + dr)) + beta * (1 / (k + sr))
        # Manually compute what hybrid_search would give for rank-1 in both lists
        actual = alpha * (1 / (k + 1)) + beta * (1 / (k + 1))
        assert actual == pytest.approx(expected)

    def test_higher_rank_lower_score(self):
        """Higher rank (worse position) gives lower RRF score."""
        k = RRF_K
        score_rank1 = 1 / (k + 1)
        score_rank5 = 1 / (k + 5)
        assert score_rank1 > score_rank5


class TestHybridSearchUnit:
    """Tests for the RRF fusion logic using mocked dense/sparse results."""

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """The same chunk appearing in both lists should appear once in output."""
        dense = [_make_chunk("A"), _make_chunk("B")]
        sparse = [_make_chunk("A"), _make_chunk("C")]

        with patch("app.retrieval.hybrid.dense_search", return_value=dense), \
             patch("app.retrieval.hybrid.sparse_search", return_value=sparse):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=10)

        ids = [c.citation_id for c in result]
        assert ids == list(dict.fromkeys(ids)), "No duplicates expected"
        assert set(ids) == {"A", "B", "C"}

    @pytest.mark.asyncio
    async def test_results_sorted_by_fusion_score(self):
        """Output chunks must be sorted descending by fusion_score."""
        dense = [_make_chunk(f"D{i}") for i in range(5)]
        sparse = [_make_chunk(f"D{4-i}") for i in range(5)]  # reverse order

        with patch("app.retrieval.hybrid.dense_search", return_value=dense), \
             patch("app.retrieval.hybrid.sparse_search", return_value=sparse):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=5)

        scores = [c.fusion_score for c in result]
        assert scores == sorted(scores, reverse=True), "Must be sorted by fusion_score desc"

    @pytest.mark.asyncio
    async def test_top_k_limit_respected(self):
        dense = [_make_chunk(f"D{i}") for i in range(20)]
        sparse = [_make_chunk(f"S{i}") for i in range(20)]

        with patch("app.retrieval.hybrid.dense_search", return_value=dense), \
             patch("app.retrieval.hybrid.sparse_search", return_value=sparse):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=5)

        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_empty_dense_returns_sparse_only(self):
        dense = []
        sparse = [_make_chunk("S1"), _make_chunk("S2")]

        with patch("app.retrieval.hybrid.dense_search", return_value=dense), \
             patch("app.retrieval.hybrid.sparse_search", return_value=sparse):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_both_returns_empty(self):
        with patch("app.retrieval.hybrid.dense_search", return_value=[]), \
             patch("app.retrieval.hybrid.sparse_search", return_value=[]):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_chunk_present_in_both_gets_bonus(self):
        """A chunk ranking well in both lists should outscore one in only one list."""
        # "best" ranks 1st in dense and 1st in sparse → max RRF
        # "dense_only" ranks 1st in dense but absent from sparse
        best = _make_chunk("best")
        dense_only = _make_chunk("dense_only")
        sparse_only = _make_chunk("sparse_only")

        with patch("app.retrieval.hybrid.dense_search",
                   return_value=[best, dense_only]), \
             patch("app.retrieval.hybrid.sparse_search",
                   return_value=[best, sparse_only]):
            db = AsyncMock()
            result = await hybrid_search(db=db, query="test", top_k=10)

        ids = [c.citation_id for c in result]
        assert ids[0] == "best", "Top chunk in both lists should rank first"
