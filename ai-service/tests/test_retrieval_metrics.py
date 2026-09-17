"""
Evaluation metrics unit tests — no DB or ML dependencies required.

Tests cover: Recall@K, Precision@K, MRR, NDCG@K, AP, MAP, edge cases.
"""

import math
import pytest
from app.evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    average_precision,
    ndcg_at_k,
    evaluate,
    RetrievalResult,
)


# ── Recall@K ──────────────────────────────────────────────────

class TestRecallAtK:
    def test_all_relevant_retrieved(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert recall_at_k(retrieved, relevant, k=3) == 1.0

    def test_partial_recall(self):
        retrieved = ["a", "x", "y", "b", "z"]
        relevant = {"a", "b", "c"}
        # Only a, b in top-5; c not retrieved
        assert recall_at_k(retrieved, relevant, k=5) == pytest.approx(2 / 3)

    def test_zero_recall_wrong_docs(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        assert recall_at_k(retrieved, relevant, k=3) == 0.0

    def test_k_smaller_than_list(self):
        retrieved = ["a", "b", "c"]
        relevant = {"c"}
        assert recall_at_k(retrieved, relevant, k=2) == 0.0
        assert recall_at_k(retrieved, relevant, k=3) == 1.0

    def test_empty_relevant_returns_zero(self):
        retrieved = ["a", "b"]
        assert recall_at_k(retrieved, set(), k=2) == 0.0

    def test_empty_retrieved(self):
        assert recall_at_k([], {"a", "b"}, k=5) == 0.0


# ── Precision@K ───────────────────────────────────────────────

class TestPrecisionAtK:
    def test_all_relevant(self):
        assert precision_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0

    def test_half_relevant(self):
        assert precision_at_k(["a", "x", "b", "y"], {"a", "b"}, k=4) == 0.5

    def test_k_zero_returns_zero(self):
        assert precision_at_k(["a"], {"a"}, k=0) == 0.0

    def test_none_relevant(self):
        assert precision_at_k(["x", "y"], {"a"}, k=2) == 0.0


# ── MRR ───────────────────────────────────────────────────────

class TestReciprocalRank:
    def test_first_is_relevant(self):
        assert reciprocal_rank(["a", "b", "c"], {"a"}) == pytest.approx(1.0)

    def test_second_is_relevant(self):
        assert reciprocal_rank(["x", "a", "b"], {"a"}) == pytest.approx(0.5)

    def test_third_is_relevant(self):
        assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)

    def test_none_relevant(self):
        assert reciprocal_rank(["x", "y"], {"a"}) == 0.0

    def test_empty_retrieved(self):
        assert reciprocal_rank([], {"a"}) == 0.0


# ── Average Precision ─────────────────────────────────────────

class TestAveragePrecision:
    def test_perfect_ranking(self):
        # Both relevant docs at top 2
        retrieved = ["a", "b", "x", "y"]
        relevant = {"a", "b"}
        # P@1 * rel(1) + P@2 * rel(2) = 1/2 * (1/1 + 2/2) = 1.0
        assert average_precision(retrieved, relevant) == pytest.approx(1.0)

    def test_reverse_ranking(self):
        # Relevant docs at bottom
        retrieved = ["x", "y", "a", "b"]
        relevant = {"a", "b"}
        # Hit at rank 3: P@3=1/3, Hit at rank 4: P@4=2/4
        # AP = (1/3 + 2/4) / 2 = (0.333 + 0.5) / 2 ≈ 0.4167
        ap = average_precision(retrieved, relevant)
        assert ap == pytest.approx((1 / 3 + 2 / 4) / 2, rel=1e-3)

    def test_no_hits(self):
        assert average_precision(["x", "y"], {"a"}) == 0.0

    def test_empty_relevant(self):
        assert average_precision(["a", "b"], set()) == 0.0


# ── NDCG@K ────────────────────────────────────────────────────

class TestNdcgAtK:
    def test_perfect_ranking(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert ndcg_at_k(retrieved, relevant, k=3) == pytest.approx(1.0)

    def test_single_relevant_at_top(self):
        retrieved = ["a", "x", "y"]
        relevant = {"a"}
        # DCG = 1/log2(2) = 1; IDCG = 1 → NDCG = 1.0
        assert ndcg_at_k(retrieved, relevant, k=3) == pytest.approx(1.0)

    def test_single_relevant_at_second(self):
        retrieved = ["x", "a", "y"]
        relevant = {"a"}
        # DCG = 1/log2(3) ≈ 0.631; IDCG = 1/log2(2) = 1 → NDCG ≈ 0.631
        expected = (1 / math.log2(3)) / (1 / math.log2(2))
        assert ndcg_at_k(retrieved, relevant, k=3) == pytest.approx(expected, rel=1e-3)

    def test_empty_relevant(self):
        assert ndcg_at_k(["a", "b"], set(), k=2) == 0.0

    def test_k_zero(self):
        assert ndcg_at_k(["a"], {"a"}, k=0) == 0.0

    def test_no_hits(self):
        assert ndcg_at_k(["x", "y"], {"a"}, k=2) == 0.0


# ── Aggregate: evaluate() ─────────────────────────────────────

class TestEvaluate:
    def test_perfect_retrieval(self):
        results = [
            RetrievalResult("q1", ["a", "b", "c"], {"a", "b", "c"}),
            RetrievalResult("q2", ["d", "e"], {"d", "e"}),
        ]
        summary = evaluate(results, k_values=[1, 5])
        assert summary.num_queries == 2
        assert summary.recall_at_k[5] == pytest.approx(1.0)
        assert summary.mrr == pytest.approx(1.0)
        assert summary.map_score == pytest.approx(1.0)

    def test_empty_results(self):
        summary = evaluate([])
        assert summary.num_queries == 0
        assert summary.mrr == 0.0

    def test_mixed_results(self):
        results = [
            RetrievalResult("q1", ["a", "x", "y"], {"a"}),  # MRR=1, R@3=1
            RetrievalResult("q2", ["x", "y", "z"], {"a"}),  # MRR=0, R@3=0
        ]
        summary = evaluate(results, k_values=[3])
        assert summary.mrr == pytest.approx(0.5)  # mean(1, 0)
        assert summary.recall_at_k[3] == pytest.approx(0.5)  # mean(1, 0)

    def test_to_dict(self):
        results = [RetrievalResult("q1", ["a"], {"a"})]
        d = evaluate(results, k_values=[1]).to_dict()
        assert "mrr" in d
        assert "map" in d
        assert "recall@k" in d
        assert "precision@k" in d
        assert "ndcg@k" in d
        assert "1" in d["recall@k"]
