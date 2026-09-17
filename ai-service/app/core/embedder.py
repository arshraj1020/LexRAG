"""
Local embedding generation using Sentence Transformers.

No API key required. Model is downloaded once and cached locally.
Dimension is configurable via EMBEDDING_DIMENSION env var.
"""

import logging
from functools import lru_cache
from typing import Union
from sentence_transformers import SentenceTransformer
from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load embedding model once and keep in memory for the process lifetime."""
    logger.info("Loading embedding model: %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)
    actual_dim = model.get_sentence_embedding_dimension()
    if actual_dim != settings.embedding_dimension:
        logger.warning(
            "Model dimension %d does not match EMBEDDING_DIMENSION=%d. "
            "Update the env var and re-run migrations before indexing.",
            actual_dim, settings.embedding_dimension,
        )
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of text strings.

    Returns a list of float vectors, one per input text.
    Batch-processed for efficiency on M2 chip.
    """
    if not texts:
        return []
    model = _load_model()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,  # cosine similarity = dot product after normalisation
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]


def get_embedding_dimension() -> int:
    """Return the actual dimension of the loaded model."""
    model = _load_model()
    return model.get_sentence_embedding_dimension()
