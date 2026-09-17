"""
Retrieval Evaluation Metrics for LexRAG.

Implements standard IR evaluation metrics:
  - Recall@K: fraction of relevant docs retrieved in top-K
  - Precision@K: fraction of top-K results that are relevant
  - MRR (Mean Reciprocal Rank): position of the first relevant result
  - NDCG@K (Normalized Discounted Cumulative Gain): ranked quality
  - AP (Average Precision): area under precision-recall curve
  - MAP (Mean Average Precision): mean of AP across queries

All functions are pure (no DB/IO) and operate on lists of IDs.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result for one query."""
    query: str
    retrieved_ids: list[str]       # ordered list of retrieved citation IDs
    relevant_ids: set[str]         # ground-truth relevant IDs


@dataclass
class MetricSummary:
    """Aggregated metrics across multiple queries."""
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg_at_k: dict[int, float] = field(default_factory=dict)
    map_score: float = 0.0
    num_queries: int = 0

    def to_dict(self) -> dict:
        return {
            "num_queries": self.num_queries,
            "mrr": round(self.mrr, 4),
            "map": round(self.map_score, 4),
            "recall@k": {str(k): round(v, 4) for k, v in self.recall_at_k.items()},
            "precision@k": {str(k): round(v, 4) for k, v in self.precision_at_k.items()},
            "ndcg@k": {str(k): round(v, 4) for k, v in self.ndcg_at_k.items()},
        }


# ── Single-query metrics ──────────────────────────────────────

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """
    Fraction of relevant documents found in the top-K retrieved results.

    recall@K = |relevant ∩ retrieved[:K]| / |relevant|

    Returns 0.0 if relevant set is empty.
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """
    Fraction of top-K results that are relevant.

    precision@K = |relevant ∩ retrieved[:K]| / K

    Returns 0.0 if k == 0.
    """
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / k


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """
    Reciprocal rank of the first relevant document.

    RR = 1 / rank_of_first_relevant (1-indexed), or 0 if none found.
    """
    for rank, doc_id in enumerate(retrieved, 1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def average_precision(retrieved: list[str], relevant: set[str]) -> float:
    """
    Area under the precision-recall curve (Average Precision).

    AP = sum(precision@k * relevance(k)) / |relevant|
    where relevance(k) = 1 if retrieved[k] is relevant else 0.

    Returns 0.0 if no relevant documents exist.
    """
    if not relevant:
        return 0.0

    hits = 0
    running_sum = 0.0
    for rank, doc_id in enumerate(retrieved, 1):
        if doc_id in relevant:
            hits += 1
            running_sum += hits / rank

    return running_sum / len(relevant)


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """
    Normalised Discounted Cumulative Gain at K.

    Uses binary relevance (1 if relevant, 0 otherwise).
    DCG@K = sum(rel_i / log2(i+1)) for i in [1..K]
    NDCG@K = DCG@K / IDCG@K (ideal ranking)

    Returns 0.0 if no relevant documents exist.
    """
    if not relevant or k == 0:
        return 0.0

    def dcg(ranked: list[str], k: int) -> float:
        return sum(
            (1.0 / math.log2(rank + 1))
            for rank, doc_id in enumerate(ranked[:k], 1)
            if doc_id in relevant
        )

    actual_dcg = dcg(retrieved, k)
    # Ideal: all relevant docs at the top
    ideal_list = list(relevant) + [""] * max(0, k - len(relevant))
    ideal_dcg = dcg(ideal_list, k)

    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


# ── Batch / aggregate metrics ─────────────────────────────────

def evaluate(
    results: list[RetrievalResult],
    k_values: Optional[list[int]] = None,
) -> MetricSummary:
    """
    Compute aggregate metrics across a list of retrieval results.

    Args:
        results: one entry per query with retrieved_ids and relevant_ids
        k_values: cut-off values for @K metrics (default: [1, 5, 10, 20])

    Returns:
        MetricSummary with averaged metrics across all queries
    """
    if k_values is None:
        k_values = [1, 5, 10, 20]

    if not results:
        return MetricSummary(num_queries=0)

    recall_sums: dict[int, float] = {k: 0.0 for k in k_values}
    precision_sums: dict[int, float] = {k: 0.0 for k in k_values}
    ndcg_sums: dict[int, float] = {k: 0.0 for k in k_values}
    mrr_sum = 0.0
    ap_sum = 0.0

    for r in results:
        for k in k_values:
            recall_sums[k] += recall_at_k(r.retrieved_ids, r.relevant_ids, k)
            precision_sums[k] += precision_at_k(r.retrieved_ids, r.relevant_ids, k)
            ndcg_sums[k] += ndcg_at_k(r.retrieved_ids, r.relevant_ids, k)
        mrr_sum += reciprocal_rank(r.retrieved_ids, r.relevant_ids)
        ap_sum += average_precision(r.retrieved_ids, r.relevant_ids)

    n = len(results)
    return MetricSummary(
        recall_at_k={k: recall_sums[k] / n for k in k_values},
        precision_at_k={k: precision_sums[k] / n for k in k_values},
        ndcg_at_k={k: ndcg_sums[k] / n for k in k_values},
        mrr=mrr_sum / n,
        map_score=ap_sum / n,
        num_queries=n,
    )
