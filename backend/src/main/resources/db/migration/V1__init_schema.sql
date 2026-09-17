-- =============================================================
-- LexRAG Database Schema — Initial Migration
-- =============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255)    NOT NULL UNIQUE,
    full_name       VARCHAR(100)    NOT NULL,
    password_hash   TEXT            NOT NULL,
    role            VARCHAR(20)     NOT NULL DEFAULT 'USER',
    enabled         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- ── Documents ─────────────────────────────────────────────────
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id            UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename   VARCHAR(255)    NOT NULL,
    storage_path        VARCHAR(512)    NOT NULL,
    file_size_bytes     BIGINT          NOT NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'UPLOADED',
    error_message       TEXT,
    title               VARCHAR(255)    NOT NULL,
    -- Legal metadata (may be null if not extractable)
    case_name           VARCHAR(500),
    court               VARCHAR(200),
    jurisdiction        VARCHAR(100),
    case_number         VARCHAR(100),
    case_year           VARCHAR(50),
    judges              VARCHAR(500),
    document_type       VARCHAR(100),
    language            VARCHAR(10),
    page_count          INTEGER,
    chunk_count         INTEGER,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ
);

CREATE INDEX idx_documents_owner   ON documents(owner_id);
CREATE INDEX idx_documents_status  ON documents(status);
CREATE INDEX idx_documents_created ON documents(created_at DESC);

-- ── Document Chunks (stored/searched via AI service through pgvector) ──
-- NOTE: The embedding column dimension must match EMBEDDING_DIMENSION env var.
-- Default: 384 (all-MiniLM-L6-v2). Change before first run if using a different model.
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID            NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER         NOT NULL,
    page_number     INTEGER,
    paragraph_number INTEGER,
    section         VARCHAR(200),
    text            TEXT            NOT NULL,
    -- Stable citation reference: DOC_{short_id}_P{page}_PAR{para}
    citation_id     VARCHAR(100)    NOT NULL UNIQUE,
    -- Denormalised for fast retrieval without joins
    case_name       VARCHAR(500),
    court           VARCHAR(200),
    case_year       VARCHAR(50),
    -- Vector embedding (dimension configurable — must match model)
    embedding       vector(384),
    -- Full-text search
    text_search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunks_document  ON document_chunks(document_id);
CREATE INDEX idx_chunks_citation  ON document_chunks(citation_id);
CREATE INDEX idx_chunks_page      ON document_chunks(document_id, page_number);
-- IVFFlat index for approximate nearest-neighbour vector search
-- Lists value (~100) should be tuned once real data volume is known.
CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- GIN index for full-text keyword search
CREATE INDEX idx_chunks_fts       ON document_chunks USING GIN (text_search_vector);

-- ── Research Sessions ─────────────────────────────────────────
CREATE TABLE research_sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255)    NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_sessions_user    ON research_sessions(user_id);
CREATE INDEX idx_research_sessions_created ON research_sessions(created_at DESC);

-- ── Research Queries ──────────────────────────────────────────
CREATE TABLE research_queries (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID            NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
    question            TEXT            NOT NULL,
    answer_text         TEXT,
    answer_json         TEXT,
    citations_json      TEXT,
    latency_ms          BIGINT,
    retrieval_strategy  VARCHAR(50),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_queries_session ON research_queries(session_id);
CREATE INDEX idx_research_queries_created ON research_queries(created_at DESC);
