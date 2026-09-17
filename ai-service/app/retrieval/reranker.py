"""
Neural Reranker using Sentence Transformers Cross-Encoder.

Cross-encoders score (query, passage) pairs jointly for much higher
accuracy than bi-encoder similarity alone. Used after hybrid retrieval
to select the best top-K chunks for the LLM context window.

Free model — no API key. Runs locally on Apple Silicon via PyTorch MPS.
"""

import logging
from functools import lru_cache
from sentence_transformers import CrossEncoder
from .dense import RetrievedChunk
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _load_reranker() -> CrossEncoder:
    logger.info("Loading cross-encoder reranker: %s", settings.reranker_model)
    return CrossEncoder(settings.reranker_model)


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    """
    Score (query, chunk) pairs with a cross-encoder and return top_k.

    Input chunks are typically the top 20-50 from hybrid retrieval.
    Output is the top_k most relevant for LLM context.
    """
    if not chunks:
        return []

    reranker = _load_reranker()
    pairs = [(query, chunk.text) for chunk in chunks]

    scores = reranker.predict(pairs, show_progress_bar=False)

    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = float(score)

    reranked = sorted(chunks, key=lambda c: c.rerank_score, reverse=True)
    return reranked[:top_k]
