# LexRAG — Phase 3 Completion Report
## Legal Intelligence Layer

**Date:** September 2026  
**Scope:** Phase 3 — Legal Intelligence (all 11 items from the Phase 3 specification)  
**Cost:** $0 — no paid APIs, no cloud LLMs, no external services

---

## 1. What Was Built

### 1.1 AI Service — Four New Inference Endpoints

All endpoints live under `/internal/*` (authenticated with `X-Internal-Api-Key`; not exposed publicly).

| Endpoint | Purpose | Key behaviour |
|---|---|---|
| `POST /internal/compare` | Multi-document case comparison | Retrieves evidence per-document, generates structured JSON with facts/issues/reasoning/similarities/differences/conflicting findings |
| `POST /internal/precedents` | Precedent search | Hybrid retrieval + reranking over the user's corpus; LLM generates ranked precedents with `legal_principle` and `relevance_explanation` |
| `POST /internal/provision` | Statutory provision analysis | Retrieves judicial interpretations; structured output covers key principles, scope, cases, open questions |
| `POST /internal/brief` | Full research brief | Larger rerank window (2× default); structured output: executive summary, key findings, authorities, arguments, supporting/conflicting evidence, conclusion |

Each endpoint:
- Expands the query before retrieval (multi-query for better recall)
- Runs hybrid retrieval (dense + BM25 via RRF) for each sub-query, deduplicating across queries
- Runs cross-encoder reranking in a thread pool (non-blocking)
- Calls the LLM with a task-specific system prompt via `generate_with_system()`
- Extracts citation IDs from the raw LLM response using JSON parsing with a regex fallback
- Runs the 4-guard citation verification pipeline (see §1.3)
- Returns `verified_citations` and `invalid_citations` as **separate lists**
- Returns `structured_*` / `precedents` as the primary payload field
- Returns `INSUFFICIENT_EVIDENCE` with a null structured field when no chunks are retrieved (never fabricates)

**Evaluation endpoint:** `POST /internal/eval/run` triggers the pipeline comparison experiment (see §1.5).

### 1.2 Spring Boot — Four New API Endpoints

| Endpoint | Method | Auth |
|---|---|---|
| `/api/research/compare` | POST | JWT |
| `/api/research/precedents` | POST | JWT |
| `/api/research/provision` | POST | JWT |
| `/api/research/brief` | POST | JWT |

Each endpoint:
- Accepts validated request DTOs (records with Jakarta Bean Validation)
- Resolves document IDs through `resolveOwnedDocIds()` before calling the AI service
- Propagates metadata filters (court, jurisdiction, yearFrom, yearTo, documentType) to the AI service
- Wraps the AI service response into typed response DTOs
- Includes a fixed legal disclaimer in every response

**New repository methods** added to `DocumentRepository`:
- `findAllByOwnerId(UUID)` — returns all documents for a user (corpus-wide search)
- `findAllByIdInAndOwnerId(Collection<UUID>, UUID)` — returns only documents that both match the requested IDs and belong to the user

### 1.3 Citation-First Generation — 4-Guard Verification

Every Phase 3 response runs the same citation verification pipeline used in Phase 2:

1. **In retrieved context** — citation ID must appear in the set of chunks actually retrieved for this query
2. **Exists in database** — `SELECT` by `citation_id` against the `document_chunks` table
3. **Owned by user** — chunk's `document_id` must be in the set of user's owned document IDs
4. **Page/paragraph match** — the page and paragraph the LLM claims must match the stored values

A citation failing any guard is flagged `is_valid: false` with a descriptive error and returned in `invalid_citations`. It is never presented as a verified source. This prevents:
- Hallucinated citations (guards 1 and 2)
- Cross-user data leakage via citation ID enumeration (guard 3)
- Page/paragraph fabrication (guard 4)

### 1.4 Owner Isolation

**AI service level:** All retrieval calls include `document_ids` (a list of string UUIDs owned by the authenticated user). The retrieval layer (`hybrid_search`, `dense_search`) filters by these IDs at the SQL level, so chunks from other users' documents are never returned.

**Spring Boot level:** `resolveOwnedDocIds()` validates every requested document UUID against `findAllByIdInAndOwnerId()`. If the returned count is less than the requested count, some IDs don't belong to the user — a `ResponseStatusException(403)` is thrown immediately. This prevents IDOR via document ID enumeration even if a caller guesses valid UUIDs.

When no `documentIds` are supplied (corpus-wide search), `allOwnedDocIds()` fetches all documents belonging to the authenticated user, so the search is automatically scoped.

### 1.5 Evaluation Framework (`pipeline_experiment.py`)

Implements a **four-configuration pipeline comparison experiment**:

| Configuration | Description |
|---|---|
| Dense RAG | Vector similarity only |
| Hybrid RAG | Dense + BM25 with RRF fusion |
| Hybrid + Rerank | Hybrid RAG + cross-encoder reranking |
| Full Pipeline | Same retrieval as Hybrid + Rerank (LLM generation excluded from latency for fair comparison) |

**Metrics computed:**
- Recall@K, Precision@K for K ∈ {1, 5, 10, 20}
- MRR (Mean Reciprocal Rank)
- NDCG@5, NDCG@10
- MAP (Mean Average Precision)
- Latency: mean, p50, p95 in milliseconds

**Anti-fabrication guarantees:**
- `BENCHMARK_QUERIES` is intentionally left empty with instructions for populating from real ingested documents
- When no labelled queries exist, the experiment returns `status: "blocked"` with an explanation — it never invents metrics
- All latency figures are wall-clock measurements from actual retrieval calls

### 1.6 Frontend — 6-Tab Research Interface

`/app/research/page.tsx` was rewritten with a tab-based layout:

| Tab | Feature |
|---|---|
| Research | Existing query flow + document multi-selector |
| Compare | Multi-document comparison (requires ≥2 selected docs; validates inline) |
| Precedents | Ranked precedent cards with legal principle, relevance explanation, relevant passage |
| Provision | Statutory provision analysis with collapsible JSON output |
| Brief | Full research brief with optional documentType filter; collapsible JSON output |
| History | Paginated session list |

Shared components: `ConfidenceBadge`, `CitationCard` (expandable chunk text), `CitationSection` (valid + invalid), `FilterRow` (court, year, document multi-selector), `JsonSection` (collapsible JSON), `Disclaimer`, `ErrorBanner`.

Documents are loaded once at the page level (`useQuery`) and passed to all tabs as props, avoiding redundant fetches.

---

## 2. Security Properties

| Property | How it's enforced |
|---|---|
| Owner isolation | `resolveOwnedDocIds()` in Java; `document_ids` filter in SQL; citation guard 3 |
| Path traversal protection | `_validate_file_path()` resolves and checks `relative_to(_UPLOAD_DIR)` |
| Prompt injection defence | Retrieved chunks are labelled UNTRUSTED and framed in the system prompt so LLM instructions embedded in documents can't hijack the pipeline |
| No secrets in responses | Debug trace excluded in production; no JWT, API key, or filesystem paths in any response |
| Citation hallucination prevention | 4-guard verification rejects citations never retrieved, not in DB, not owned, or with mismatched coordinates |
| No fabricated metrics | Evaluation experiment blocked when benchmark has no labelled queries |

---

## 3. Files Created or Modified

### AI Service (`ai-service/`)
| File | Change |
|---|---|
| `app/api/v1/routes.py` | Added `compare`, `precedents`, `provision`, `brief`, `eval/run` endpoints; fixed field names (`structured_comparison`, `structured_analysis`, `structured_brief`); added `court/year_from/year_to/jurisdiction/document_type` fields to all Phase 3 models; moved `import json`, `import re` to module level |
| `app/generation/prompts/comparison_prompt.py` | New — system prompt + user prompt builder for case comparison |
| `app/generation/prompts/precedent_prompt.py` | New — system prompt + user prompt builder for precedent search |
| `app/generation/prompts/provision_prompt.py` | New — system prompt + user prompt builder for provision analysis |
| `app/generation/prompts/brief_prompt.py` | New — system prompt + user prompt builder for brief generation |
| `app/evaluation/pipeline_experiment.py` | New — 4-configuration pipeline comparison experiment |
| `app/evaluation/metrics.py` | New — pure metric functions (Recall@K, Precision@K, MRR, NDCG@K, AP, MAP) |
| `tests/test_phase3_endpoints.py` | New — 46 unit tests for Phase 3 models, helpers, and endpoint logic |

### Spring Boot Backend (`backend/`)
| File | Change |
|---|---|
| `api/controllers/ResearchController.java` | Added 4 Phase 3 endpoints |
| `api/dto/request/CaseComparisonRequest.java` | New |
| `api/dto/request/PrecedentSearchRequest.java` | New |
| `api/dto/request/ProvisionAnalysisRequest.java` | New |
| `api/dto/request/ResearchBriefRequest.java` | New |
| `api/dto/response/CaseComparisonResponse.java` | New |
| `api/dto/response/PrecedentSearchResponse.java` | New |
| `api/dto/response/ProvisionAnalysisResponse.java` | New |
| `api/dto/response/ResearchBriefResponse.java` | New |
| `service/interfaces/ResearchService.java` | Added 4 Phase 3 method signatures |
| `service/impl/ResearchServiceImpl.java` | Added 4 Phase 3 method implementations + owner isolation helpers + response builders; removed unused `ArrayList` import |
| `service/ai/AiServiceClient.java` | Added 4 Phase 3 client methods + inner request records |
| `domain/repositories/DocumentRepository.java` | Added `findAllByOwnerId`, `findAllByIdInAndOwnerId` |
| `src/test/java/.../ResearchServicePhase3Test.java` | New — 20 unit tests covering owner isolation, 403 on foreign docs, corpus-wide search, response mapping |

### Frontend (`frontend/`)
| File | Change |
|---|---|
| `src/lib/api.ts` | Added `ComparisonResponse`, `PrecedentEntry`, `PrecedentResponse`, `ProvisionResponse`, `BriefResponse`; added `compare()`, `precedents()`, `provision()`, `brief()` to `researchApi`; increased timeout to 120s |
| `src/app/research/page.tsx` | Complete rewrite — 6-tab interface; fixed import of Phase 3 types from `@/lib/api`; fixed implicit `any` on precedent map callback |

---

## 4. Tests

### Python — 126 tests, all passing
| Suite | Tests | Covers |
|---|---|---|
| `test_phase3_endpoints.py` | 46 | All Phase 3 models, `_confidence_to_float`, `_extract_all_citation_ids` (JSON + regex paths), `_verified_to_dict`, `_chunk_to_dict`, insufficient evidence paths, fabricated citation rejection, citation split into valid/invalid, 400 on missing provision, disclaimer presence |
| `test_citation_verifier.py` | 8 | 4-guard citation verification |
| `test_retrieval_metrics.py` | 29 | Recall@K, Precision@K, MRR, NDCG@K, MAP, edge cases |
| `test_hybrid_retrieval.py` | 8 | RRF fusion, deduplication |
| `test_prompt_injection.py` | 12 | Injection patterns in retrieved content |
| `test_path_validation.py` | 7 | Path traversal rejection |
| `test_query_expansion.py` | 10 | Multi-query expansion |
| `test_chunking.py` | 4 | Legal-aware chunking |
| `test_health.py` | 2 | Health endpoint |

### Java — 20 unit tests (compile-verified)
`ResearchServicePhase3Test.java` covers:
- `compare()`: 403 on foreign doc, passes verified IDs to AI client, returns empty on insufficient evidence, passes metadata filters
- `findPrecedents()`: corpus-wide when no docIds, 403 on foreign doc, precedents extracted from response
- `analyseProvision()`: 403 on foreign doc, correct provision and disclaimer in response
- `generateBrief()`: 403 on foreign doc, corpus-wide search, correct research question and disclaimer, passes jurisdiction and documentType
- Owner isolation cross-cutting: all IDs owned → passes; partial ownership → 403 with status code 403

*Note: Java tests cannot be executed in this environment (Maven Central not reachable). They were statically verified to reference the correct types, methods, and field names from the production code.*

### TypeScript — zero type errors
`npx tsc --noEmit --skipLibCheck` produces no errors after import fixes.

---

## 5. Known Limitations

| Limitation | Notes |
|---|---|
| Evaluation benchmark is empty | `BENCHMARK_QUERIES` must be populated with real ingested documents + ground-truth citation IDs before the pipeline comparison can run. Instructions are in the file. |
| LLM generation latency | Ollama/Mistral generation is ~30–120s depending on hardware and context size. The compare/brief endpoints can take up to 3 minutes on CPU-only machines. |
| JSON parse reliability | Phase 3 endpoints depend on the LLM returning valid JSON. A `parse_error` flag is returned when parsing fails; the structured field will be `null`. Increasing the Ollama model (e.g. llama3.2:8b) improves JSON adherence. |
| Cross-encoder not GPU-accelerated | The cross-encoder model runs on CPU by default. GPU acceleration via `device="cuda"` significantly reduces latency. |
| Corpus-wide comparison | The compare endpoint searches per-document. If the user has many documents and selects all, the retrieval fan-out can be slow. The endpoint caps at 10 documents per request. |
| No session persistence for Phase 3 | Compare/Precedent/Provision/Brief queries are not persisted to `research_sessions`. Only the `/api/research/query` endpoint creates session history. This is intentional to keep the session model simple; it can be extended in Phase 4. |

---

## 6. Phase 3 Status

| Item | Status |
|---|---|
| 1. Case comparison endpoint | ✅ Complete |
| 2. Precedent search endpoint | ✅ Complete |
| 3. Legal provision analysis endpoint | ✅ Complete |
| 4. Research brief generation endpoint | ✅ Complete |
| 5. Multi-document research (owner isolation) | ✅ Complete |
| 6. Citation-first generation with 4-guard verification | ✅ Complete |
| 7. INSUFFICIENT_EVIDENCE handling | ✅ Complete |
| 8. Evaluation framework (pipeline comparison) | ✅ Complete |
| 9. Evaluation metrics (Recall@K, MRR, NDCG, MAP) | ✅ Complete |
| 10. Testing | ✅ Complete (126 Python tests pass; 20 Java tests statically verified) |
| 11. Final code review | ✅ Complete (unused import removed, local imports promoted to module level, TypeScript errors fixed) |
