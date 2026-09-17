# LexRAG — Architecture

## Overview

LexRAG is a free, local, citation-grounded AI Legal Research Intelligence Platform. It combines:

- **Spring Boot** — authentication, document management, REST API orchestration
- **FastAPI** — all AI/ML pipeline: PDF extraction, chunking, embeddings, retrieval, reranking, LLM generation
- **PostgreSQL + pgvector** — relational data + vector similarity search
- **Ollama** — local LLM inference on Apple Silicon (no API keys)
- **Next.js** — professional legal research frontend

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js (port 3000)                     │
│         Legal Research UI — Dashboard, Documents,           │
│         Research, Cases, History                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/JSON (JWT)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Spring Boot (port 8080)                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ AuthService  │  │DocumentService│  │ResearchService  │  │
│  │ JWT/Security │  │Upload/Status │  │Sessions/History │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                          │                    │             │
│              PostgreSQL (JPA/Flyway)          │             │
└──────────────────────────┼────────────────────┼────────────-┘
                           │ X-Internal-Api-Key │
                           ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI AI Service (port 8001)             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Ingestion Pipeline                    │    │
│  │  PDF → OCR → Text → Metadata → Chunks → Embeddings │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │Dense Retrieve│  │Sparse (FTS)  │  │Hybrid (RRF)     │  │
│  │pgvector cosine│ │PostgreSQL FTS│  │Dense + Sparse   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                          │                                  │
│                    ┌─────▼──────┐                           │
│                    │ Cross-Enc  │  (neural reranker)        │
│                    └─────┬──────┘                           │
│                          │                                  │
│                    ┌─────▼──────┐                           │
│                    │   Ollama   │  (local LLM)              │
│                    └─────┬──────┘                           │
│                          │                                  │
│              ┌───────────▼───────────┐                      │
│              │ Citation Verifier     │                      │
│              └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
   PostgreSQL + pgvector              Redis (cache)
   - users                           - rate limits
   - documents                       - session cache
   - document_chunks
   - research_sessions
   - research_queries
```

## Responsibility Separation

| Concern | Owner |
|---------|-------|
| Authentication / JWT | Spring Boot |
| User management / RBAC | Spring Boot |
| Document metadata (DB) | Spring Boot |
| Document ownership enforcement | Spring Boot |
| Research session storage | Spring Boot |
| REST API surface | Spring Boot |
| Rate limiting | Spring Boot |
| PDF extraction / OCR | FastAPI |
| Legal-aware chunking | FastAPI |
| Embedding generation | FastAPI |
| Vector search (pgvector) | FastAPI |
| Full-text keyword search | FastAPI |
| Hybrid retrieval + RRF | FastAPI |
| Neural reranking | FastAPI |
| Query expansion | FastAPI |
| LLM generation (Ollama) | FastAPI |
| Citation generation | FastAPI |
| Citation verification | FastAPI |
| RAG evaluation | FastAPI |

## Security Model

- JWT tokens expire after 24h (configurable)
- Every document query enforces `owner_id = current_user.id`
- Internal AI service endpoints require `X-Internal-Api-Key`
- File uploads validated for MIME type and size
- No secrets in Git — all config via environment variables
- Retrieved legal documents treated as untrusted input (prompt injection defence)

## Technology Choices

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Ollama (mistral/llama3.2) | Free, local, Apple Silicon support |
| Embeddings | sentence-transformers | Free, local, high quality |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Free, local, state-of-art reranking |
| Vector DB | PostgreSQL + pgvector | No separate service, transactional |
| Keyword search | PostgreSQL FTS (tsvector) | Built-in, legal term matching |
| Fusion | Reciprocal Rank Fusion (RRF) | Parameter-free, robust |
| OCR | Tesseract | Free, accurate for legal docs |
| PDF parsing | PyMuPDF | Fast, preserves block structure |
