# LexRAG — Evaluation Framework

## Structure

```
evaluation/
├── datasets/
│   └── questions.json          # Benchmark query set (populate with real ingested docs)
├── experiments/
│   └── .gitkeep                # Pipeline comparison scripts live in ai-service/app/evaluation/
├── results/
│   └── .gitkeep                # Generated results — NOT committed to git
└── README.md
```

## Running Evaluations

The pipeline comparison experiment is implemented in the AI service and exposed
as an authenticated internal endpoint:

```
POST /internal/eval/run
X-Internal-Api-Key: <key>
```

This triggers `ai-service/app/evaluation/pipeline_experiment.py`, which compares:

| Configuration      | Description                                 |
|--------------------|---------------------------------------------|
| Dense RAG          | Vector similarity only                      |
| Hybrid RAG         | Dense + BM25 with RRF fusion                |
| Hybrid + Rerank    | Hybrid RAG + cross-encoder reranking        |
| Full Pipeline      | Hybrid + Rerank (LLM excluded for latency)  |

**Metrics:** Recall@K, Precision@K, MRR, NDCG@K, MAP, latency (mean/p50/p95)

## Benchmark Queries

Populate `datasets/questions.json` with real ingested document citation IDs
before running. The experiment returns `status: "blocked"` when no labelled
queries are present — it **never fabricates metrics**.

## Results

Raw results land in `evaluation/results/` and are excluded from git via `.gitignore`.
