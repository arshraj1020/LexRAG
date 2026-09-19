"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Search, Loader2, AlertCircle, CheckCircle, XCircle,
  Scale, FileSearch, BookOpen, FileText, History, ChevronDown, ChevronUp,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import {
  researchApi, documentsApi,
  type ComparisonResponse, type PrecedentResponse,
  type ProvisionResponse, type BriefResponse,
} from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import type { Citation, SearchFilters } from "@/types";

// ── Tab definitions ───────────────────────────────────────────────────────────

type TabId = "query" | "compare" | "precedents" | "provision" | "brief" | "history";

const TABS: Array<{ id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: "query",      label: "Research",    icon: Search      },
  { id: "compare",    label: "Compare",     icon: Scale       },
  { id: "precedents", label: "Precedents",  icon: FileSearch  },
  { id: "provision",  label: "Provision",   icon: BookOpen    },
  { id: "brief",      label: "Brief",       icon: FileText    },
  { id: "history",    label: "History",     icon: History     },
];

// ── Shared sub-components ────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }: { confidence: number | string | null }) {
  let label: string;
  if (confidence == null) {
    label = "N/A";
  } else if (typeof confidence === "number") {
    label = confidence >= 0.7 ? "HIGH" : confidence >= 0.4 ? "MEDIUM" : "LOW";
  } else {
    label = (confidence as string).toUpperCase();
  }
  const colorClass =
    label === "HIGH"   ? "bg-green-100 text-green-700"
    : label === "MEDIUM" ? "bg-yellow-100 text-yellow-700"
    : label === "LOW"    ? "bg-red-100 text-red-700"
    : "bg-gray-100 text-gray-600";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {label} confidence
    </span>
  );
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-lg border p-3 ${citation.is_valid ? "bg-blue-50 border-blue-200" : "bg-red-50 border-red-200"}`}>
      <div className="flex items-start gap-2">
        <span className="flex-shrink-0 font-mono text-xs text-gray-500">[{index}]</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            {citation.is_valid
              ? <CheckCircle className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
              : <XCircle    className="h-3.5 w-3.5 text-red-600 flex-shrink-0" />}
            <span className="text-xs font-mono text-gray-500 truncate">{citation.citation_id}</span>
          </div>
          {citation.case_name && (
            <p className="text-xs font-medium text-gray-700">
              {citation.case_name}{citation.court ? ` — ${citation.court}` : ""}
            </p>
          )}
          <p className="text-xs text-gray-500">Page {citation.page} · ¶{citation.paragraph}</p>
          {citation.claim && (
            <p className="text-xs text-gray-600 mt-1 italic">&quot;{citation.claim}&quot;</p>
          )}
          {!citation.is_valid && citation.validation_errors?.map((e, i) => (
            <p key={i} className="text-xs text-red-600 mt-1">⚠ {e}</p>
          ))}
          {citation.chunk_text && (
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1 text-xs text-blue-600 mt-1 hover:underline"
            >
              {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {open ? "Hide evidence" : "Show evidence"}
            </button>
          )}
          {open && citation.chunk_text && (
            <p className="mt-2 text-xs text-gray-700 bg-white rounded p-2 border border-blue-100 leading-relaxed">
              {citation.chunk_text}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function CitationSection({
  verified,
  invalid,
}: { verified: Citation[]; invalid: Citation[] }) {
  if (!verified.length && !invalid.length) return null;
  return (
    <div className="card p-6">
      <h3 className="font-semibold text-gray-900 mb-3 text-sm">
        Sources ({verified.length} verified{invalid.length > 0 ? `, ${invalid.length} flagged` : ""})
      </h3>
      <div className="space-y-2">
        {verified.map((c, i) => <CitationCard key={c.citation_id} index={i + 1} citation={c} />)}
        {invalid.map((c, i) => <CitationCard key={c.citation_id} index={verified.length + i + 1} citation={c} />)}
      </div>
    </div>
  );
}

function FilterRow({
  filters,
  onChange,
  showDocSelector = false,
  documents = [],
  selectedDocs = [],
  onDocToggle,
  minDocs,
}: {
  filters: SearchFilters;
  onChange: (f: SearchFilters) => void;
  showDocSelector?: boolean;
  documents?: Array<{ id: string; title: string; status: string }>;
  selectedDocs?: string[];
  onDocToggle?: (id: string) => void;
  minDocs?: number;
}) {
  return (
    <div className="space-y-3">
      {showDocSelector && onDocToggle && (
        <div>
          <p className="text-xs text-gray-500 mb-1">
            Documents {minDocs ? `(select ≥${minDocs})` : "(optional — leave unselected for all)"}
          </p>
          <div className="flex flex-wrap gap-2">
            {documents.filter((d) => d.status === "READY").map((d) => (
              <button
                key={d.id}
                onClick={() => onDocToggle(d.id)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  selectedDocs.includes(d.id)
                    ? "bg-primary-600 text-white border-primary-600"
                    : "bg-white text-gray-700 border-gray-300 hover:border-primary-400"
                }`}
              >
                {d.title}
              </button>
            ))}
            {documents.filter((d) => d.status === "READY").length === 0 && (
              <span className="text-xs text-gray-400 italic">No ready documents</span>
            )}
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <input
          className="border border-gray-300 rounded px-2 py-1.5 text-xs w-36"
          placeholder="Court (optional)"
          value={filters.court ?? ""}
          onChange={(e) => onChange({ ...filters, court: e.target.value || undefined })}
        />
        <input
          type="number"
          className="border border-gray-300 rounded px-2 py-1.5 text-xs w-24"
          placeholder="From year"
          value={filters.yearFrom ?? ""}
          onChange={(e) => onChange({ ...filters, yearFrom: e.target.value ? +e.target.value : undefined })}
        />
        <input
          type="number"
          className="border border-gray-300 rounded px-2 py-1.5 text-xs w-24"
          placeholder="To year"
          value={filters.yearTo ?? ""}
          onChange={(e) => onChange({ ...filters, yearTo: e.target.value ? +e.target.value : undefined })}
        />
      </div>
    </div>
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  const msg = (error as any)?.response?.data?.message
    ?? (error as any)?.response?.data?.detail
    ?? "Request failed. Please try again.";
  return (
    <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
      <AlertCircle className="h-4 w-4 flex-shrink-0" />
      {msg}
    </div>
  );
}

function Disclaimer({ text }: { text?: string }) {
  return (
    <p className="text-xs text-gray-400 text-center px-4">
      {text ?? "AI-assisted legal research. Verify all citations with primary sources. Not legal advice."}
    </p>
  );
}

function JsonSection({ title, data }: { title: string; data: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(true);
  if (!data) return null;
  return (
    <div className="card p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 font-semibold text-gray-900 text-sm w-full text-left"
      >
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        {title}
      </button>
      {open && (
        <pre className="mt-3 text-xs bg-gray-50 rounded p-3 overflow-auto max-h-96 border border-gray-200">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

/**
 * Shown in place of the structured result when the AI service found no
 * relevant evidence (structuredComparison/structuredAnalysis/structuredBrief
 * comes back null — see ResearchServiceImpl.extractStructured on the backend).
 *
 * Without this, the Compare/Provision/Brief tabs previously rendered nothing
 * but a bare (and misleadingly non-"N/A") confidence badge, giving no
 * indication of why the result panel looked empty — the same pattern the
 * Research tab already handles explicitly for INSUFFICIENT_EVIDENCE answers.
 */
function InsufficientEvidenceBanner() {
  return (
    <div className="card p-6 text-sm text-amber-700 flex gap-2 items-center">
      <AlertCircle className="h-4 w-4 flex-shrink-0" />
      Insufficient evidence in the uploaded documents to answer this request.
    </div>
  );
}

// ── Query tab ─────────────────────────────────────────────────────────────────

import type { ResearchAnswer } from "@/types";

function QueryTab({ documents }: { documents: Array<{ id: string; title: string; status: string }> }) {
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({ strategy: "HYBRID_RERANK" });
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [result, setResult] = useState<ResearchAnswer | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchApi.query({
        question,
        strategy: filters.strategy,
        documentIds: selectedDocs.length ? selectedDocs : undefined,
        court: filters.court,
        yearFrom: filters.yearFrom,
        yearTo: filters.yearTo,
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const toggleDoc = useCallback((id: string) => {
    setSelectedDocs((ds) => ds.includes(id) ? ds.filter((d) => d !== id) : [...ds, id]);
  }, []);

  return (
    <div className="space-y-6">
      <form onSubmit={(e) => { e.preventDefault(); if (question.trim()) mutation.mutate(); }} className="card p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Research Question</label>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          rows={3}
          placeholder="e.g. What factors did the court consider when granting anticipatory bail?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="mt-3 space-y-3">
          <div className="flex items-center gap-3">
            <select
              className="border border-gray-300 rounded px-2 py-1.5 text-xs"
              value={filters.strategy}
              onChange={(e) => setFilters((f) => ({ ...f, strategy: e.target.value as any }))}
            >
              <option value="DENSE">Dense (fastest)</option>
              <option value="HYBRID">Hybrid</option>
              <option value="HYBRID_RERANK">Hybrid + Rerank (best)</option>
            </select>
          </div>
          <FilterRow
            filters={filters}
            onChange={setFilters}
            showDocSelector
            documents={documents}
            selectedDocs={selectedDocs}
            onDocToggle={toggleDoc}
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button type="submit" disabled={!question.trim() || mutation.isPending} className="btn-primary">
            {mutation.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Researching…</>
              : <><Search className="h-4 w-4" /> Research</>}
          </button>
        </div>
      </form>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {result && (
        <div className="space-y-4">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Answer</h2>
              <ConfidenceBadge confidence={result.confidence} />
            </div>
            {result.answer === "INSUFFICIENT_EVIDENCE" ? (
              <div className="flex items-center gap-2 text-amber-700 text-sm">
                <AlertCircle className="h-4 w-4" />
                Insufficient evidence in the uploaded documents to answer this question.
              </div>
            ) : (
              <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
            )}
            <div className="mt-4 pt-4 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
              <span>{result.retrievedChunks} chunks retrieved</span>
              <span>Strategy: {result.strategy}</span>
              <span>{result.latencyMs}ms</span>
            </div>
          </div>
          <CitationSection
            verified={result.verifiedCitations?.filter((c) => c.is_valid) ?? []}
            invalid={result.verifiedCitations?.filter((c) => !c.is_valid) ?? []}
          />
          <Disclaimer text={result.disclaimer} />
        </div>
      )}
    </div>
  );
}

// ── Compare tab ───────────────────────────────────────────────────────────────

function CompareTab({ documents }: { documents: Array<{ id: string; title: string; status: string }> }) {
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [result, setResult] = useState<ComparisonResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchApi.compare({
        question,
        documentIds: selectedDocs,
        court: filters.court,
        yearFrom: filters.yearFrom,
        yearTo: filters.yearTo,
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const toggleDoc = useCallback((id: string) => {
    setSelectedDocs((ds) => ds.includes(id) ? ds.filter((d) => d !== id) : [...ds, id]);
  }, []);

  const canSubmit = question.trim() && selectedDocs.length >= 2 && !mutation.isPending;

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Comparison Question</label>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          rows={3}
          placeholder="e.g. How do these cases differ in their approach to the standard of proof?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="mt-3">
          <FilterRow
            filters={filters}
            onChange={setFilters}
            showDocSelector
            documents={documents}
            selectedDocs={selectedDocs}
            onDocToggle={toggleDoc}
            minDocs={2}
          />
        </div>
        {selectedDocs.length > 0 && selectedDocs.length < 2 && (
          <p className="mt-2 text-xs text-amber-600">Select at least 2 documents to compare.</p>
        )}
        <div className="mt-4 flex justify-end">
          <button
            disabled={!canSubmit}
            onClick={() => mutation.mutate()}
            className="btn-primary"
          >
            {mutation.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Comparing…</>
              : <><Scale className="h-4 w-4" /> Compare Cases</>}
          </button>
        </div>
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {result && (
        <div className="space-y-4">
          {result.structuredComparison === null && <InsufficientEvidenceBanner />}
          <JsonSection title="Structured Comparison" data={result.structuredComparison} />
          <CitationSection verified={result.verifiedCitations ?? []} invalid={result.invalidCitations ?? []} />
          <div className="flex items-center gap-3 text-xs text-gray-400 px-1">
            {result.structuredComparison !== null && <ConfidenceBadge confidence={result.confidence} />}
            <span>{result.latencyMs}ms</span>
          </div>
          <Disclaimer text={result.disclaimer} />
        </div>
      )}
    </div>
  );
}

// ── Precedents tab ────────────────────────────────────────────────────────────

function PrecedentsTab({ documents }: { documents: Array<{ id: string; title: string; status: string }> }) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [topK, setTopK] = useState(10);
  const [result, setResult] = useState<PrecedentResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchApi.precedents({
        query,
        documentIds: selectedDocs.length ? selectedDocs : undefined,
        court: filters.court,
        yearFrom: filters.yearFrom,
        yearTo: filters.yearTo,
        topK,
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const toggleDoc = useCallback((id: string) => {
    setSelectedDocs((ds) => ds.includes(id) ? ds.filter((d) => d !== id) : [...ds, id]);
  }, []);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Precedent Query</label>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          rows={3}
          placeholder="e.g. Cases establishing the doctrine of promissory estoppel in contract law"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-600">Top K results:</label>
            <input
              type="number"
              min={1} max={25}
              value={topK}
              onChange={(e) => setTopK(+e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-xs w-16"
            />
          </div>
          <FilterRow
            filters={filters}
            onChange={setFilters}
            showDocSelector
            documents={documents}
            selectedDocs={selectedDocs}
            onDocToggle={toggleDoc}
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button
            disabled={!query.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
            className="btn-primary"
          >
            {mutation.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Searching…</>
              : <><FileSearch className="h-4 w-4" /> Find Precedents</>}
          </button>
        </div>
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {result && (
        <div className="space-y-4">
          {result.precedents.length === 0 ? (
            <div className="card p-6 text-sm text-amber-700 flex gap-2 items-center">
              <AlertCircle className="h-4 w-4" />
              No precedents found for this query.
            </div>
          ) : (
            <div className="space-y-3">
              {result.precedents.map((p: import("@/lib/api").PrecedentEntry, i: number) => (
                <div key={p.citation_id ?? i} className="card p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <span className="text-xs font-mono text-gray-400 mr-2">#{p.rank ?? i + 1}</span>
                      <span className="font-medium text-sm text-gray-900">{p.case_name ?? "Unknown Case"}</span>
                    </div>
                    {p.court && (
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded flex-shrink-0">
                        {p.court}
                      </span>
                    )}
                  </div>
                  {p.legal_principle && (
                    <p className="text-xs font-medium text-blue-700 mb-1">Principle: {p.legal_principle}</p>
                  )}
                  {p.relevance_explanation && (
                    <p className="text-xs text-gray-600 mb-2">{p.relevance_explanation}</p>
                  )}
                  {p.relevant_passage && (
                    <p className="text-xs text-gray-500 italic border-l-2 border-blue-200 pl-2">
                      &quot;{p.relevant_passage}&quot;
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                    {p.year && <span>{p.year}</span>}
                    <span className="font-mono">{p.citation_id}</span>
                    {p.page != null && <span>p.{p.page} ¶{p.paragraph}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
          <CitationSection verified={result.verifiedCitations ?? []} invalid={result.invalidCitations ?? []} />
          <div className="flex items-center gap-3 text-xs text-gray-400 px-1">
            <span>{result.retrievedChunks} chunks retrieved</span>
            <ConfidenceBadge confidence={result.confidence} />
            <span>{result.latencyMs}ms</span>
          </div>
          <Disclaimer text={result.disclaimer} />
        </div>
      )}
    </div>
  );
}

// ── Provision tab ─────────────────────────────────────────────────────────────

function ProvisionTab({ documents }: { documents: Array<{ id: string; title: string; status: string }> }) {
  const [provision, setProvision] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [result, setResult] = useState<ProvisionResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchApi.provision({
        provision,
        documentIds: selectedDocs.length ? selectedDocs : undefined,
        court: filters.court,
        yearFrom: filters.yearFrom,
        yearTo: filters.yearTo,
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const toggleDoc = useCallback((id: string) => {
    setSelectedDocs((ds) => ds.includes(id) ? ds.filter((d) => d !== id) : [...ds, id]);
  }, []);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Statutory Provision</label>
        <input
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          placeholder="e.g. Section 34 IPC, Article 21 Constitution of India, Section 482 CrPC"
          value={provision}
          onChange={(e) => setProvision(e.target.value)}
        />
        <p className="mt-1 text-xs text-gray-400">
          Analysis is derived from retrieved case judgments, not statutory databases.
          Not authoritative legal interpretation.
        </p>
        <div className="mt-3">
          <FilterRow
            filters={filters}
            onChange={setFilters}
            showDocSelector
            documents={documents}
            selectedDocs={selectedDocs}
            onDocToggle={toggleDoc}
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button
            disabled={!provision.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
            className="btn-primary"
          >
            {mutation.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Analysing…</>
              : <><BookOpen className="h-4 w-4" /> Analyse Provision</>}
          </button>
        </div>
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {result && (
        <div className="space-y-4">
          {result.structuredAnalysis === null && <InsufficientEvidenceBanner />}
          <JsonSection title="Judicial Interpretation Analysis" data={result.structuredAnalysis} />
          <CitationSection verified={result.verifiedCitations ?? []} invalid={result.invalidCitations ?? []} />
          <div className="flex items-center gap-3 text-xs text-gray-400 px-1">
            {result.structuredAnalysis !== null && <ConfidenceBadge confidence={result.confidence} />}
            <span>{result.latencyMs}ms</span>
          </div>
          <Disclaimer text={result.disclaimer} />
        </div>
      )}
    </div>
  );
}

// ── Brief tab ─────────────────────────────────────────────────────────────────

function BriefTab({ documents }: { documents: Array<{ id: string; title: string; status: string }> }) {
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [docType, setDocType] = useState("");
  const [result, setResult] = useState<BriefResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      researchApi.brief({
        researchQuestion: question,
        documentIds: selectedDocs.length ? selectedDocs : undefined,
        court: filters.court,
        yearFrom: filters.yearFrom,
        yearTo: filters.yearTo,
        documentType: docType || undefined,
      }).then((r) => r.data),
    onSuccess: (data) => setResult(data),
  });

  const toggleDoc = useCallback((id: string) => {
    setSelectedDocs((ds) => ds.includes(id) ? ds.filter((d) => d !== id) : [...ds, id]);
  }, []);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Research Question</label>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          rows={4}
          placeholder="e.g. What is the legal position on punitive damages for breach of fiduciary duty under Indian law?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <p className="mt-1 text-xs text-gray-400">
          A comprehensive brief will be generated covering key findings, authorities,
          arguments, supporting and conflicting evidence, and open questions.
          Expect 30–120s generation time.
        </p>
        <div className="mt-3 space-y-2">
          <input
            className="border border-gray-300 rounded px-2 py-1.5 text-xs w-40"
            placeholder="Document type (optional)"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          />
          <FilterRow
            filters={filters}
            onChange={setFilters}
            showDocSelector
            documents={documents}
            selectedDocs={selectedDocs}
            onDocToggle={toggleDoc}
          />
        </div>
        <div className="mt-4 flex justify-end">
          <button
            disabled={!question.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
            className="btn-primary"
          >
            {mutation.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating Brief…</>
              : <><FileText className="h-4 w-4" /> Generate Brief</>}
          </button>
        </div>
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {result && (
        <div className="space-y-4">
          {result.structuredBrief === null && <InsufficientEvidenceBanner />}
          <JsonSection title="Research Brief" data={result.structuredBrief} />
          <CitationSection verified={result.verifiedCitations ?? []} invalid={result.invalidCitations ?? []} />
          <div className="flex items-center gap-3 text-xs text-gray-400 px-1">
            <span>{result.retrievedChunks} chunks retrieved</span>
            {result.structuredBrief !== null && <ConfidenceBadge confidence={result.confidence} />}
            <span>{result.latencyMs}ms</span>
          </div>
          <Disclaimer text={result.disclaimer} />
        </div>
      )}
    </div>
  );
}

// ── History tab ───────────────────────────────────────────────────────────────

function HistoryTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["research-sessions"],
    queryFn: () => researchApi.listSessions(0).then((r) => r.data),
  });

  if (isLoading) return (
    <div className="flex items-center gap-2 text-gray-500 text-sm p-6">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading sessions…
    </div>
  );

  if (isError) return <ErrorBanner error={null} />;

  const sessions = (data as any)?.content ?? [];

  return (
    <div className="space-y-3">
      {sessions.length === 0 ? (
        <div className="card p-8 text-center text-sm text-gray-400">
          No research sessions yet. Submit a query to get started.
        </div>
      ) : (
        sessions.map((s: any) => (
          <div key={s.id} className="card p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-sm text-gray-900">{s.title}</p>
                {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
              </div>
              <div className="text-xs text-gray-400 flex flex-col items-end gap-0.5">
                <span>{s.queryCount ?? 0} queries</span>
                <span>{new Date(s.createdAt).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("query");

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
  }, [router]);

  const { data: docsData } = useQuery({
    queryKey: ["documents-for-research"],
    queryFn: () => documentsApi.list(0, 100).then((r) => r.data),
    staleTime: 60_000,
  });

  const documents = (docsData as any)?.content ?? [];

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-serif font-bold text-gray-900 mb-1">Legal Intelligence</h1>
        <p className="text-sm text-gray-500 mb-6">
          AI-powered research grounded in your uploaded documents with verified citations.
        </p>

        {/* Tab nav */}
        <div className="flex gap-1 mb-6 overflow-x-auto border-b border-gray-200">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === id
                  ? "border-primary-600 text-primary-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "query"      && <QueryTab      documents={documents} />}
        {activeTab === "compare"    && <CompareTab    documents={documents} />}
        {activeTab === "precedents" && <PrecedentsTab documents={documents} />}
        {activeTab === "provision"  && <ProvisionTab  documents={documents} />}
        {activeTab === "brief"      && <BriefTab      documents={documents} />}
        {activeTab === "history"    && <HistoryTab />}
      </div>
    </AppShell>
  );
}
