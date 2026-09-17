# evaluation package — retrieval quality metrics (Recall@K, MRR, NDCG, MAP)
from .metrics import (
    RetrievalResult,
    MetricSummary,
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    average_precision,
    ndcg_at_k,
    evaluate,
)

__all__ = [
    "RetrievalResult",
    "MetricSummary",
    "recall_at_k",
    "precision_at_k",
    "reciprocal_rank",
    "average_precision",
    "ndcg_at_k",
    "evaluate",
]
