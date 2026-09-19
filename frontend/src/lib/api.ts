/**
 * LexRAG API Client
 *
 * Thin axios wrapper for the Spring Boot backend.
 * JWT token is attached automatically from localStorage.
 */

import axios, { AxiosError } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Must be >= the backend's own AiServiceClient.GENERATE_TIMEOUT (300s, used for
// /api/research/query, /compare, /precedents, /provision, /brief) with margin.
// A shorter client-side timeout would abort a request the backend is still
// legitimately processing and could have completed successfully, surfacing a
// spurious "Request failed" error to the user instead of the real answer.
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 310_000, // 5 min 10s — LLM generation can take up to 5 minutes server-side
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("lexrag_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 — redirect to login
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("lexrag_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── Auth endpoints ────────────────────────────────────────────

export interface RegisterPayload { email: string; fullName: string; password: string }
export interface LoginPayload    { email: string; password: string }
export interface AuthResponse    { token: string; userId: string; email: string; fullName: string; role: string }

export const authApi = {
  register: (payload: RegisterPayload) =>
    api.post<AuthResponse>("/api/auth/register", payload),
  login: (payload: LoginPayload) =>
    api.post<AuthResponse>("/api/auth/login", payload),
};

// ── Document endpoints ────────────────────────────────────────

export interface DocumentSummary {
  id: string; title: string; originalFilename: string;
  status: "UPLOADED" | "PROCESSING" | "READY" | "FAILED";
  caseName?: string; court?: string; caseYear?: string;
  pageCount?: number; chunkCount?: number;
  createdAt: string; processedAt?: string; errorMessage?: string;
}

export const documentsApi = {
  list: (page = 0, size = 20) =>
    api.get<{ content: DocumentSummary[]; totalElements: number }>("/api/documents", { params: { page, size } }),
  get: (id: string) =>
    api.get<DocumentSummary>(`/api/documents/${id}`),
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<DocumentSummary>("/api/documents", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => onProgress?.(Math.round((e.loaded * 100) / (e.total ?? 1))),
    });
  },
  delete: (id: string) =>
    api.delete(`/api/documents/${id}`),
};

// ── Research endpoints ────────────────────────────────────────

// Citation objects are proxied from the AI service (Python snake_case preserved in Map values)
export interface Citation {
  citation_id: string; claim: string; page: number; paragraph: number;
  case_name?: string; court?: string; is_valid: boolean;
  validation_errors?: string[]; chunk_text?: string;
}
// Top-level response fields use camelCase (Spring Boot / Jackson default)
export interface ResearchResponse {
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
  id: string; title: string; description?: string;
  createdAt: string; updatedAt: string;
}

// ── Phase 3 response types ────────────────────────────────────

export interface ComparisonResponse {
  question: string;
  structuredComparison: Record<string, unknown> | null;
  verifiedCitations: Citation[];
  invalidCitations: Citation[];
  confidence: string | null;
  latencyMs: number;
  generatedAt: string;
  disclaimer: string;
}

export interface PrecedentEntry {
  rank: number;
  citation_id: string;
  case_name?: string;
  court?: string;
  year?: string;
  relevant_passage?: string;
  page?: number;
  paragraph?: number;
  relevance_explanation?: string;
  legal_principle?: string;
}

export interface PrecedentResponse {
  query: string;
  precedents: PrecedentEntry[];
  verifiedCitations: Citation[];
  invalidCitations: Citation[];
  retrievedChunks: number;
  confidence: string | null;
  latencyMs: number;
  generatedAt: string;
  disclaimer: string;
}

export interface ProvisionResponse {
  provision: string;
  structuredAnalysis: Record<string, unknown> | null;
  verifiedCitations: Citation[];
  invalidCitations: Citation[];
  confidence: string | null;
  latencyMs: number;
  generatedAt: string;
  disclaimer: string;
}

export interface BriefResponse {
  researchQuestion: string;
  structuredBrief: Record<string, unknown> | null;
  verifiedCitations: Citation[];
  invalidCitations: Citation[];
  retrievedChunks: number;
  confidence: string | null;
  latencyMs: number;
  generatedAt: string;
  disclaimer: string;
}

export const researchApi = {
  query: (payload: {
    question: string;
    sessionId?: string;
    documentIds?: string[];
    strategy?: string;
    court?: string;
    yearFrom?: number;
    yearTo?: number;
  }) => api.post<ResearchResponse>("/api/research/query", payload),

  listSessions: (page = 0) =>
    api.get<{ content: ResearchSession[]; totalElements: number }>("/api/research/sessions", { params: { page } }),

  getSession: (id: string) =>
    api.get(`/api/research/sessions/${id}`),

  compare: (payload: {
    question: string;
    documentIds: string[];
    court?: string;
    yearFrom?: number;
    yearTo?: number;
  }) => api.post<ComparisonResponse>("/api/research/compare", payload),

  precedents: (payload: {
    query: string;
    documentIds?: string[];
    court?: string;
    jurisdiction?: string;
    yearFrom?: number;
    yearTo?: number;
    topK?: number;
  }) => api.post<PrecedentResponse>("/api/research/precedents", payload),

  provision: (payload: {
    provision: string;
    documentIds?: string[];
    court?: string;
    yearFrom?: number;
    yearTo?: number;
  }) => api.post<ProvisionResponse>("/api/research/provision", payload),

  brief: (payload: {
    researchQuestion: string;
    documentIds?: string[];
    court?: string;
    jurisdiction?: string;
    yearFrom?: number;
    yearTo?: number;
    documentType?: string;
  }) => api.post<BriefResponse>("/api/research/brief", payload),
};
