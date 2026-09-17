// ── Auth ──────────────────────────────────────────────────────
export interface User {
  userId: string;
  email: string;
  fullName: string;
  role: "USER" | "ADMIN";
}

// ── Documents ─────────────────────────────────────────────────
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "READY" | "FAILED";

export interface LegalDocument {
  id: string;
  title: string;
  originalFilename: string;
  status: DocumentStatus;
  caseName?: string;
  court?: string;
  jurisdiction?: string;
  caseNumber?: string;
  caseYear?: string;
  judges?: string;
  documentType?: string;
  pageCount?: number;
  chunkCount?: number;
  createdAt: string;
  processedAt?: string;
  errorMessage?: string;
}

// ── Research ──────────────────────────────────────────────────
export interface Citation {
  citation_id: string;
  claim: string;
  page: number;
  paragraph: number;
  case_name?: string;
  court?: string;
  is_valid: boolean;
  validation_errors?: string[];
  chunk_text?: string;
}

// Top-level fields use camelCase (Jackson default from Spring Boot backend)
// Citation list items use snake_case (proxied from AI service Python output)
export interface ResearchAnswer {
  queryId: string;
  question: string;
  answer: string;
  verifiedCitations: Citation[];
  strategy: string;
  confidence: number | null;
  retrievedChunks: number | null;
  latencyMs: number;
  createdAt: string;
  disclaimer: string;
}

export interface ResearchSession {
  id: string;
  title: string;
  description?: string;
  queries?: ResearchQuery[];
  createdAt: string;
  updatedAt: string;
}

export interface ResearchQuery {
  id: string;
  question: string;
  answerText?: string;
  latencyMs?: number;
  retrievalStrategy?: string;
  createdAt: string;
}

// ── API Errors ────────────────────────────────────────────────
export interface ApiError {
  timestamp: string;
  status: number;
  error: string;
  message: string;
  fieldErrors?: Record<string, string>;
}

// ── Retrieval strategy ────────────────────────────────────────
export type RetrievalStrategy = "DENSE" | "HYBRID" | "HYBRID_RERANK";

// ── Filters ───────────────────────────────────────────────────
export interface SearchFilters {
  documentIds?: string[];
  court?: string;
  yearFrom?: number;
  yearTo?: number;
  strategy?: RetrievalStrategy;
}
