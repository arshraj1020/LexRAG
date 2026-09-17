# LexRAG — Repository Refactor Audit

**Date:** 2026-09-17  
**Scope:** Full structural refactor before GitHub push (no functionality changed)  
**Result:** ✅ PASSED — 126/126 Python tests, 0 TypeScript errors, 0 stale imports

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| AI Service `app/` Python files | 32 | 32 |
| AI Service package directories | 10 (fragmented) | 7 (clean) |
| Test files | 9 | 9 |
| Stale Python imports | 0 | 0 |
| Stale mock patch strings | 2 files | 0 |
| TypeScript errors | 0 | 0 |
| Broken relative import depths | 2 | 0 |

---

## AI Service — Package Restructure

### Old layout (10 packages, fragmented)

```
app/
├── config/          # settings, database, dependencies
├── embeddings/      # embedder.py (shared concern buried here)
├── extraction/      # pdf_extractor.py
├── chunking/        # legal_chunker.py
├── metadata/        # legal_metadata_extractor.py
├── ingestion/       # ingestion_pipeline.py
├── retrieval/       # dense_retriever, sparse_retriever, hybrid_retriever
├── reranking/       # cross_encoder_reranker.py
├── research/        # query_expander.py
├── generation/
│   ├── llm/         # ollama_provider.py (nested sub-package)
│   └── prompts/     # 5 prompt files
├── citations/
├── evaluation/
└── api/v1/routes.py
```

### New layout (7 packages, domain-coherent)

```
app/
├── core/            # settings, database, dependencies, embedder
│   ├── __init__.py
│   ├── settings.py
│   ├── database.py
│   ├── dependencies.py
│   └── embedder.py  # cross-cutting: used by ingestion + retrieval
├── ingestion/       # pipeline, extraction, chunking, metadata (full pipeline)
│   ├── __init__.py
│   ├── pipeline.py
│   ├── extraction.py
│   ├── chunking.py
│   └── metadata.py
├── retrieval/       # dense, sparse, hybrid, reranker, query_expander
│   ├── __init__.py
│   ├── dense.py
│   ├── sparse.py
│   ├── hybrid.py
│   ├── reranker.py
│   └── query_expander.py
├── generation/      # ollama + 5 prompt files (flat, no llm/ sub-package)
│   ├── __init__.py
│   ├── ollama.py
│   └── prompts/
│       ├── legal_research_prompt.py
│       ├── comparison_prompt.py
│       ├── precedent_prompt.py
│       ├── provision_prompt.py
│       └── brief_prompt.py
├── citations/       # citation_verifier
├── evaluation/      # pipeline_experiment, metrics, __init__
└── api/
    ├── __init__.py
    └── routes.py    # was api/v1/routes.py (flattened — no versioning needed internally)
```

---

## Files Moved / Renamed

| Old Path | New Path |
|----------|----------|
| `app/config/settings.py` | `app/core/settings.py` |
| `app/config/database.py` | `app/core/database.py` |
| `app/config/dependencies.py` | `app/core/dependencies.py` |
| `app/embeddings/embedder.py` | `app/core/embedder.py` |
| `app/extraction/pdf_extractor.py` | `app/ingestion/extraction.py` |
| `app/chunking/legal_chunker.py` | `app/ingestion/chunking.py` |
| `app/metadata/legal_metadata_extractor.py` | `app/ingestion/metadata.py` |
| `app/ingestion/ingestion_pipeline.py` | `app/ingestion/pipeline.py` |
| `app/retrieval/dense_retriever.py` | `app/retrieval/dense.py` |
| `app/retrieval/sparse_retriever.py` | `app/retrieval/sparse.py` |
| `app/retrieval/hybrid_retriever.py` | `app/retrieval/hybrid.py` |
| `app/reranking/cross_encoder_reranker.py` | `app/retrieval/reranker.py` |
| `app/research/query_expander.py` | `app/retrieval/query_expander.py` |
| `app/generation/llm/ollama_provider.py` | `app/generation/ollama.py` |
| `app/api/v1/routes.py` | `app/api/routes.py` |
| `PHASE3_REPORT.md` (root) | `docs/PHASE3_REPORT.md` |

---

## Directories Removed

| Directory | Reason |
|-----------|--------|
| `app/config/` | Renamed to `app/core/` |
| `app/embeddings/` | `embedder.py` moved to `app/core/` |
| `app/extraction/` | Merged into `app/ingestion/` |
| `app/chunking/` | Merged into `app/ingestion/` |
| `app/metadata/` | Merged into `app/ingestion/` |
| `app/reranking/` | Merged into `app/retrieval/` |
| `app/research/` | Merged into `app/retrieval/` |
| `app/generation/llm/` | Flattened into `app/generation/` |
| `app/api/v1/` | Flattened to `app/api/` |
| `tests/__init__.py` | Removed (tests use absolute imports; file was unused) |

---

## Imports Fixed

### `app/api/routes.py`
All cross-package imports corrected from `...xxx` (3-dot, invalid at depth 3) to `..xxx` (2-dot):
```python
# Before (wrong — routes.py moved up one level from api/v1/)
from ...core.database import get_db

# After (correct)
from ..core.database import get_db
```

All 10 cross-package imports updated (core, ingestion, retrieval, generation, citations).

### `app/ingestion/pipeline.py`
Old scattered imports unified:
```python
from .extraction import extract_text_from_pdf
from .chunking import chunk_document
from .metadata import extract_legal_metadata
from ..core.embedder import embed_texts
from ..core.settings import get_settings
```

### `app/retrieval/dense.py`, `sparse.py`, `hybrid.py`, `reranker.py`
All updated from `..embeddings.embedder` → `..core.embedder`, `..config.settings` → `..core.settings`, old cross-module names → new names.

### `app/generation/ollama.py`
Fixed: `from ...config.settings` → `from ..core.settings`, `from ..prompts.xxx` → `from .prompts.xxx`.

### `app/evaluation/pipeline_experiment.py`
Fixed: `from ..reranking.cross_encoder import rerank` → `from ..retrieval.reranker import rerank`.

### `main.py`
Fixed: `from app.api.v1.routes import router` → `from app.api.routes import router`.

---

## Tests Fixed

| File | Fix |
|------|-----|
| `tests/test_hybrid_retrieval.py` | All 6 `patch("app.retrieval.hybrid_retriever.*")` → `patch("app.retrieval.hybrid.*")` |
| `tests/test_path_validation.py` | `patch("app.api.v1.routes.*")` → `patch("app.api.routes.*")` |
| `tests/test_phase3_endpoints.py` | All `from app.api.v1.routes import` and `patch("app.api.v1.routes.*")` updated |
| `tests/test_chunking.py` | `from app.chunking.legal_chunker import` → `from app.ingestion.chunking import` |
| `tests/test_query_expansion.py` | `from app.research.query_expander import` → `from app.retrieval.query_expander import` |

---

## New Files Added

| File | Purpose |
|------|---------|
| `evaluation/README.md` | Documents eval framework and benchmark setup |
| `evaluation/experiments/.gitkeep` | Preserves empty dir in git |
| `evaluation/results/.gitkeep` | Preserves empty dir in git |
| `infrastructure/grafana/dashboards/.gitkeep` | Preserves empty dir in git |
| `docs/REFACTOR_AUDIT.md` | This file |

---

## Verification Results

```
Python tests:   126 passed, 0 failed, 0 errors   ✅
TypeScript:     0 errors, 0 warnings              ✅
Stale imports:  0                                 ✅
Stale patches:  0                                 ✅
Docker paths:   valid (infrastructure/docker-compose.yml) ✅
```

---

## What Was NOT Changed

- All business logic, algorithms, SQL queries, API contracts
- Spring Boot backend source (`backend/src/`)
- Frontend source (`frontend/src/`)
- Infrastructure / Docker Compose definitions
- `.env.example`, `Makefile`, root-level docs
- Phase 3 report content (moved to `docs/`, not edited)
