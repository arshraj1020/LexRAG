# LexRAG — AI Legal Research Intelligence Platform

> **Free · Local · Citation-Grounded · Research-Grade**

LexRAG is an open-source AI legal research platform that lets you upload legal judgments, ask research questions, and receive **citation-verified answers** powered by local LLMs — with zero API costs.

---

## ⚠ Legal Disclaimer

LexRAG is a **research assistance tool**. Generated content is NOT legal advice. Always verify citations against primary sources. Consult a qualified lawyer for legal matters.

---

## Features

| Feature | Status |
|---------|--------|
| PDF upload + OCR for scanned pages | ✅ |
| Legal-aware chunking (section detection) | ✅ |
| Local embeddings (Sentence Transformers) | ✅ |
| Dense vector search (pgvector) | ✅ |
| Keyword search (PostgreSQL FTS) | ✅ |
| Hybrid retrieval + RRF fusion | ✅ |
| Neural reranking (Cross-Encoder) | ✅ |
| Local LLM generation (Ollama) | ✅ |
| Citation generation (page/paragraph) | ✅ |
| Citation verification (hallucination check) | ✅ |
| Query expansion (rule-based multi-query) | ✅ |
| Prompt injection defence | ✅ |
| Path traversal protection | ✅ |
| Research session history | ✅ |
| RAG evaluation metrics (Recall, MRR, NDCG) | ✅ |
| Case comparison | ✅ |
| Precedent search | ✅ |
| Legal provision analysis | ✅ |
| Research brief generation | ✅ |
| Multi-document research | ✅ |
| Citation-first generation | ✅ |
| RAG pipeline evaluation (4 experiments) | ✅ |

---

## Architecture

```
Next.js UI → Spring Boot API → FastAPI AI Service
                                     │
                    ┌────────────────┴──────────────────┐
                    │                                   │
             PostgreSQL + pgvector              Ollama (local LLM)
             (vectors + metadata)               (mistral / llama3.2)
```

See [docs/architecture.md](docs/architecture.md) for the full system diagram.

---

## Tech Stack

**Frontend:** Next.js 15 · TypeScript · Tailwind CSS · TanStack Query

**Backend:** Java 21 · Spring Boot 3 · Spring Security · JWT · Flyway · PostgreSQL

**AI Service:** Python 3.11 · FastAPI · PyMuPDF · Tesseract · Sentence Transformers · Cross-Encoder · Ollama

**Infrastructure:** Docker Compose · PostgreSQL 16 + pgvector · Redis · Prometheus · Grafana

**Cost:** $0 — entirely free and local

---

## Prerequisites

- Docker + Docker Compose
- [Ollama](https://ollama.com) (installed inside Docker or on host)
- 16GB RAM recommended for mistral 7B
- Apple M2 / ARM64 supported natively

---

## Quick Start

### 1. Clone and configure

```bash
git clone <your-repo-url> lexrag
cd lexrag

# Copy and edit environment config
cp .env.example .env
# Edit .env: set strong passwords, JWT secret (min 64 chars)
```

### 2. Pull an Ollama model (first time only)

```bash
# Start Ollama container first
docker compose up ollama -d

# Pull a model (choose one based on RAM):
docker exec lexrag-ollama ollama pull mistral       # 7B, ~4.1GB, good balance
docker exec lexrag-ollama ollama pull llama3.2:3b   # 3B, ~2GB, faster/lighter
```

Update `LLM_MODEL` in `.env` to match your chosen model.

### 3. Start all services

```bash
docker compose up --build
```

Services:
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8080 |
| Swagger UI | http://localhost:8080/swagger-ui.html |
| AI Service | http://localhost:8001/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/changeme) |

### 4. Register and start researching

1. Open http://localhost:3000
2. Register an account
3. Upload a PDF legal judgment
4. Wait for status to become **READY** (~30s depending on document size)
5. Ask a research question on the Research page

---

## Development Setup (without Docker)

### Backend (Spring Boot)

```bash
cd backend
# Requires Java 21, Maven, and a running PostgreSQL + Redis
mvn spring-boot:run
```

### Backend tests

`mvn test` runs `LexRagApplicationTests` with `@ActiveProfiles("test")`, which
reads `backend/src/main/resources/application-test.yml`. That profile expects
its own, minimal PostgreSQL + Redis pair on localhost — deliberately separate
from the full `docker compose` stack, so tests don't need a real `.env`
(JWT secret, internal API key, etc.):

| Setting | Default |
|---|---|
| Postgres role | `lexrag` |
| Postgres password | `changeme` |
| Postgres database | `lexrag_test` |
| Redis | `localhost:6379` db `1`, no auth |

On a machine with a native PostgreSQL already installed (e.g. via
`brew services start postgresql@17`), that service normally owns
`localhost:5432` ahead of anything Docker publishes there, so the bootstrap
script creates the `lexrag` role / `lexrag_test` database directly in it via
`psql` rather than fighting it for the port. Redis still runs in a throwaway
Docker container. Run once:

```bash
./scripts/setup-test-db.sh
```

Then:

```bash
cd backend
mvn clean test
mvn clean verify
```

### AI Service (FastAPI)

```bash
cd ai-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Tesseract (macOS)
brew install tesseract

# Start
uvicorn main:app --reload --port 8001
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

---

## RAG Pipeline Experiments

LexRAG implements four retrieval configurations for systematic comparison:

| Experiment | Method | Components |
|-----------|--------|-----------|
| A | Dense RAG | Query embedding → pgvector cosine → Ollama |
| B | Hybrid RAG | Dense + FTS → RRF fusion → Ollama |
| C | Hybrid + Rerank | B + Cross-Encoder reranking |
| D | Full Pipeline | C + query expansion |

Metrics: Recall@5, Recall@10, MRR, NDCG, Faithfulness, Citation Accuracy, Latency

See [docs/rag-pipeline.md](docs/rag-pipeline.md) for the full pipeline documentation.

---

## Environment Variables

See [.env.example](.env.example) for all available configuration options with documentation.

Key variables:

```env
LLM_MODEL=mistral                           # Ollama model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384                     # Must match model
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
TOP_K=20                                    # Retrieval candidates
RERANK_TOP_K=8                              # After reranking
HYBRID_DENSE_WEIGHT=0.6
HYBRID_SPARSE_WEIGHT=0.4
```

---

## API Documentation

Spring Boot exposes Swagger UI at `/swagger-ui.html`.

Key endpoints:

```
POST /api/auth/register          Register
POST /api/auth/login             Login → JWT

POST /api/documents              Upload PDF
GET  /api/documents              List documents
GET  /api/documents/{id}         Document details
DELETE /api/documents/{id}       Delete document

POST /api/research/query         Research question → Answer + Citations
GET  /api/research/sessions      Research history
POST /api/research/compare       Compare cases
POST /api/research/precedents    Find precedents
```

---

## Project Structure

```
lexrag/
├── backend/               # Spring Boot API
│   └── src/main/java/com/lexrag/
│       ├── api/           # Controllers, DTOs
│       ├── config/        # Security, JPA config
│       ├── domain/        # Entities, repositories
│       ├── service/       # Business logic
│       └── security/      # JWT, filters
│
├── ai-service/            # FastAPI AI pipeline
│   └── app/
│       ├── extraction/    # PDF + OCR
│       ├── chunking/      # Legal-aware chunker
│       ├── embeddings/    # Sentence Transformers
│       ├── retrieval/     # Dense, sparse, hybrid
│       ├── reranking/     # Cross-Encoder
│       ├── generation/    # Ollama LLM + prompts
│       ├── citations/     # Citation verifier
│       └── ingestion/     # Full pipeline orchestration
│
├── frontend/              # Next.js UI
│   └── src/
│       ├── app/           # Pages (research, documents, etc.)
│       ├── components/    # UI components
│       ├── lib/           # API client
│       └── types/         # TypeScript types
│
├── infrastructure/        # Docker Compose, Prometheus, Grafana
├── evaluation/            # Benchmark datasets and results
└── docs/                  # Architecture and pipeline docs
```

---

## Contributing

1. Follow the phase-by-phase build plan in [docs/architecture.md](docs/architecture.md)
2. Use Conventional Commits: `feat(rag): add cross-encoder reranking`
3. Write tests before marking a phase complete
4. Do not claim metrics until actually measured

---

## Limitations

- LLM quality depends on the Ollama model selected — larger models give better answers but are slower
- Embedding quality depends on the sentence-transformers model — `all-MiniLM-L6-v2` is fast but `BAAI/bge-base-en-v1.5` may be more accurate
- OCR quality varies for low-resolution scans
- Legal metadata extraction uses heuristics — complex documents may require manual correction
- Query expansion is rule-based (acronym + section→concept mapping) — no LLM-based query rewriting yet

## License

MIT
