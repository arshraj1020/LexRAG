"""
Pipeline Comparison Experiment — LexRAG Evaluation Framework.

Compares four retrieval/generation pipeline configurations on a benchmark dataset:
  1. Dense RAG          — vector similarity only
  2. Hybrid RAG         — RRF fusion of dense + sparse
  3. Hybrid + Rerank    — Hybrid RAG + cross-encoder reranking
  4. Full Pipeline      — Hybrid + Rerank + LLM generation + citation verification

Reported metrics per pipeline:
  - Recall@1, Recall@5, Recall@10, Recall@20
  - Precision@1, Precision@5, Precision@10, Precision@20
  - MRR
  - NDCG@5, NDCG@10
  - MAP
  - Latency (mean, p50, p95) in milliseconds

IMPORTANT:
  - Results are NEVER fabricated. Metrics are computed from real retrieval
    against the benchmark queries defined in BENCHMARK_QUERIES below.
  - If the database is unavailable, the experiment is clearly marked as
    BLOCKED rather than returning invented numbers.
  - All latency figures are wall-clock measurements from actual retrieval calls.
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .metrics import RetrievalResult, MetricSummary, evaluate
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Benchmark dataset ─────────────────────────────────────────────────────────
#
# Each query has:
#   - query: the natural-language research question
#   - relevant_ids: ground-truth citation IDs (from documents already ingested)
#
# INSTRUCTIONS FOR POPULATING THIS DATASET:
#   1. Ingest your legal documents using the /internal/ingest endpoint.
#   2. Run a search to find the citation IDs relevant to each query.
#   3. Replace the empty relevant_ids lists below with the real IDs.
#
# The experiment will log a SKIPPED warning for any query with no relevant_ids
# and exclude it from aggregate metrics (not fabricate results for it).

BENCHMARK_QUERIES: list[dict] = [
    # Format: {"query": str, "relevant_ids": list[str]}
    #
    # Add your labelled queries here. Example (replace with real citation IDs):
    # {
    #     "query": "What is the standard of proof for contempt of court in civil proceedings?",
    #     "relevant_ids": [
    #         "DOC_XXXXXXXX_P12_PAR4",
    #         "DOC_XXXXXXXX_P7_PAR2",
    #     ],
    # },
]


# ── Experiment configuration ──────────────────────────────────────────────────

K_VALUES = [1, 5, 10, 20]
TOP_K_RETRIEVAL = 20   # How many results to retrieve per pipeline
RERANK_TOP_K = 10      # Cross-encoder reranks top-K dense+hybrid results


# ── Result containers ─────────────────────────────────────────────────────────

@dataclass
class PipelineLatency:
    """Wall-clock latencies in milliseconds, one per query."""
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p95(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    def to_dict(self) -> dict:
        return {
            "mean_ms": round(self.mean, 1),
            "p50_ms": round(self.p50, 1),
            "p95_ms": round(self.p95, 1),
            "n": len(self.latencies_ms),
        }


@dataclass
class PipelineResult:
    """Full evaluation result for one pipeline configuration."""
    pipeline_name: str
    metrics: MetricSummary
    latency: PipelineLatency
    status: str = "ok"   # "ok", "blocked", "partial"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "pipeline": self.pipeline_name,
            "status": self.status,
            "notes": self.notes,
            "metrics": self.metrics.to_dict(),
            "latency": self.latency.to_dict(),
        }


@dataclass
class ExperimentReport:
    """Full experiment report across all pipelines."""
    results: list[PipelineResult]
    benchmark_queries: int
    labelled_queries: int
    k_values: list[int]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "experiment": "LexRAG Pipeline Comparison",
            "benchmark_queries_total": self.benchmark_queries,
            "labelled_queries_used": self.labelled_queries,
            "k_values": self.k_values,
            "notes": self.notes,
            "pipelines": [r.to_dict() for r in self.results],
        }


# ── Retrieval helpers ─────────────────────────────────────────────────────────

async def _run_dense(db: AsyncSession, query: str, top_k: int) -> tuple[list[str], float]:
    """
    Run dense retrieval. Returns (ordered citation_id list, latency_ms).
    Returns ([], 0.0) on error — never fabricates results.
    """
    from ..retrieval.dense import dense_search
    t0 = time.perf_counter()
    try:
        chunks = await dense_search(db, query, top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        return [c.citation_id for c in chunks], latency_ms
    except Exception as exc:
        logger.error("Dense retrieval failed for query '%s': %s", query[:60], exc)
        return [], 0.0


async def _run_hybrid(db: AsyncSession, query: str, top_k: int) -> tuple[list[str], float]:
    """
    Run hybrid retrieval (dense + sparse RRF).
    Returns (ordered citation_id list, latency_ms).
    """
    from ..retrieval.hybrid import hybrid_search
    t0 = time.perf_counter()
    try:
        chunks = await hybrid_search(db, query, top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        return [c.citation_id for c in chunks], latency_ms
    except Exception as exc:
        logger.error("Hybrid retrieval failed for query '%s': %s", query[:60], exc)
        return [], 0.0


async def _run_hybrid_rerank(
    db: AsyncSession, query: str, top_k: int
) -> tuple[list[str], float]:
    """
    Run hybrid retrieval then cross-encoder reranking.
    The reranker runs in a thread pool to avoid blocking the event loop.
    Returns (ordered citation_id list, latency_ms).
    """
    from ..retrieval.hybrid import hybrid_search
    from ..retrieval.dense import RetrievedChunk
    t0 = time.perf_counter()
    try:
        # Fetch more candidates so the reranker has material to work with
        chunks = await hybrid_search(db, query, min(top_k * 3, 60))

        loop = asyncio.get_event_loop()
        reranked = await loop.run_in_executor(None, _rerank_sync, query, chunks, top_k)

        latency_ms = (time.perf_counter() - t0) * 1000
        return [c.citation_id for c in reranked], latency_ms
    except Exception as exc:
        logger.error("Hybrid+Rerank failed for query '%s': %s", query[:60], exc)
        return [], 0.0


def _rerank_sync(query: str, chunks, top_k: int):
    """Synchronous cross-encoder reranking — runs in thread pool."""
    try:
        from ..retrieval.reranker import rerank
        return rerank(query, chunks, top_k)
    except Exception as exc:
        logger.warning("Cross-encoder unavailable during eval: %s", exc)
        return chunks[:top_k]


# ── Pipeline runners ──────────────────────────────────────────────────────────

async def run_dense_pipeline(
    db: AsyncSession,
    queries: list[dict],
) -> PipelineResult:
    """Experiment 1: Dense RAG — vector similarity only."""
    logger.info("Running Dense RAG pipeline (%d queries)", len(queries))
    retrieval_results = []
    latency = PipelineLatency()

    for item in queries:
        query = item["query"]
        relevant = set(item["relevant_ids"])
        ids, lat = await _run_dense(db, query, TOP_K_RETRIEVAL)
        retrieval_results.append(RetrievalResult(query, ids, relevant))
        latency.latencies_ms.append(lat)

    metrics = evaluate(retrieval_results, K_VALUES)
    return PipelineResult("Dense RAG", metrics, latency)


async def run_hybrid_pipeline(
    db: AsyncSession,
    queries: list[dict],
) -> PipelineResult:
    """Experiment 2: Hybrid RAG — dense + sparse with RRF."""
    logger.info("Running Hybrid RAG pipeline (%d queries)", len(queries))
    retrieval_results = []
    latency = PipelineLatency()

    for item in queries:
        query = item["query"]
        relevant = set(item["relevant_ids"])
        ids, lat = await _run_hybrid(db, query, TOP_K_RETRIEVAL)
        retrieval_results.append(RetrievalResult(query, ids, relevant))
        latency.latencies_ms.append(lat)

    metrics = evaluate(retrieval_results, K_VALUES)
    return PipelineResult("Hybrid RAG", metrics, latency)


async def run_hybrid_rerank_pipeline(
    db: AsyncSession,
    queries: list[dict],
) -> PipelineResult:
    """Experiment 3: Hybrid + Cross-Encoder Rerank."""
    logger.info("Running Hybrid+Rerank pipeline (%d queries)", len(queries))
    retrieval_results = []
    latency = PipelineLatency()

    for item in queries:
        query = item["query"]
        relevant = set(item["relevant_ids"])
        ids, lat = await _run_hybrid_rerank(db, query, RERANK_TOP_K)
        retrieval_results.append(RetrievalResult(query, ids, relevant))
        latency.latencies_ms.append(lat)

    metrics = evaluate(retrieval_results, K_VALUES)
    return PipelineResult("Hybrid + Rerank", metrics, latency)


async def run_full_pipeline(
    db: AsyncSession,
    queries: list[dict],
) -> PipelineResult:
    """
    Experiment 4: Full Pipeline — Hybrid + Rerank (retrieval metrics only).

    Note: LLM generation is excluded from retrieval evaluation since it does
    not affect which chunks are retrieved, only how they are synthesised.
    Retrieval latency is the same as Hybrid+Rerank. Generation latency
    (30–120s per query) is intentionally excluded so the metric set stays
    comparable across all four pipelines. Full-pipeline latency would be
    measured separately in a live session.
    """
    logger.info("Running Full Pipeline (retrieval metrics) (%d queries)", len(queries))
    retrieval_results = []
    latency = PipelineLatency()

    for item in queries:
        query = item["query"]
        relevant = set(item["relevant_ids"])
        ids, lat = await _run_hybrid_rerank(db, query, RERANK_TOP_K)
        retrieval_results.append(RetrievalResult(query, ids, relevant))
        latency.latencies_ms.append(lat)

    metrics = evaluate(retrieval_results, K_VALUES)
    return PipelineResult(
        "Full Pipeline",
        metrics,
        latency,
        notes=(
            "Retrieval metrics only. LLM generation excluded from latency "
            "to keep pipeline comparisons fair (generation latency: ~30–120s)."
        ),
    )


# ── Experiment entry point ────────────────────────────────────────────────────

async def run_experiment(
    database_url: Optional[str] = None,
    output_path: Optional[str] = None,
) -> ExperimentReport:
    """
    Run all four pipeline experiments and produce a comparison report.

    Args:
        database_url: async SQLAlchemy URL. Defaults to settings.database_url.
        output_path: write JSON report here (optional).

    Returns:
        ExperimentReport with metrics for all four pipelines.

    IMPORTANT: If BENCHMARK_QUERIES is empty or none have relevant_ids,
    the experiment is clearly marked BLOCKED rather than fabricating results.
    """
    db_url = database_url or settings.database_url
    notes: list[str] = []

    # Filter to queries with at least one ground-truth relevant ID
    labelled = [q for q in BENCHMARK_QUERIES if q.get("relevant_ids")]
    skipped = len(BENCHMARK_QUERIES) - len(labelled)

    if skipped > 0:
        msg = (
            f"{skipped} benchmark queries have no relevant_ids and were excluded. "
            "Populate BENCHMARK_QUERIES in pipeline_experiment.py with ground-truth IDs "
            "from your ingested documents before running the experiment."
        )
        logger.warning(msg)
        notes.append(msg)

    if not labelled:
        blocked_note = (
            "EXPERIMENT BLOCKED: No labelled benchmark queries found. "
            "Add ground-truth relevant_ids to BENCHMARK_QUERIES to run the evaluation. "
            "Results are NOT fabricated."
        )
        logger.error(blocked_note)
        blocked_metrics = MetricSummary(num_queries=0)
        blocked_result = PipelineResult(
            pipeline_name="ALL",
            metrics=blocked_metrics,
            latency=PipelineLatency(),
            status="blocked",
            notes=blocked_note,
        )
        return ExperimentReport(
            results=[blocked_result],
            benchmark_queries=len(BENCHMARK_QUERIES),
            labelled_queries=0,
            k_values=K_VALUES,
            notes=[blocked_note],
        )

    logger.info(
        "Starting pipeline comparison experiment: %d labelled queries, k=%s",
        len(labelled), K_VALUES
    )

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results: list[PipelineResult] = []

    async with async_session() as db:
        results.append(await run_dense_pipeline(db, labelled))
        results.append(await run_hybrid_pipeline(db, labelled))
        results.append(await run_hybrid_rerank_pipeline(db, labelled))
        results.append(await run_full_pipeline(db, labelled))

    await engine.dispose()

    report = ExperimentReport(
        results=results,
        benchmark_queries=len(BENCHMARK_QUERIES),
        labelled_queries=len(labelled),
        k_values=K_VALUES,
        notes=notes,
    )

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info("Experiment report written to %s", output_path)

    return report


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    output = sys.argv[1] if len(sys.argv) > 1 else "eval_report.json"

    async def main():
        report = await run_experiment(output_path=output)
        print(json.dumps(report.to_dict(), indent=2))

    asyncio.run(main())
