"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText, Upload, Trash2, AlertCircle, CheckCircle,
  Clock, Loader2, RefreshCw, XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { documentsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import type { DocumentSummary } from "@/lib/api";

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: DocumentSummary["status"] }) {
  const cfg = {
    UPLOADED:   { label: "Queued",     icon: Clock,        cls: "bg-gray-100 text-gray-600" },
    PROCESSING: { label: "Processing", icon: Loader2,      cls: "bg-blue-100 text-blue-700" },
    READY:      { label: "Ready",      icon: CheckCircle,  cls: "bg-green-100 text-green-700" },
    FAILED:     { label: "Failed",     icon: XCircle,      cls: "bg-red-100 text-red-700" },
  }[status] ?? { label: status, icon: AlertCircle, cls: "bg-gray-100 text-gray-600" };

  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      <Icon className={`h-3 w-3 flex-shrink-0 ${status === "PROCESSING" ? "animate-spin" : ""}`} />
      {cfg.label}
    </span>
  );
}

// ── Upload area ──────────────────────────────────────────────────────────────

function UploadArea({ onUploadComplete }: { onUploadComplete: () => void }) {
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => documentsApi.upload(file, setProgress).then((r) => r.data),
    onSuccess: () => {
      setProgress(null);
      setUploadError(null);
      onUploadComplete();
    },
    onError: (err: any) => {
      setProgress(null);
      setUploadError(err?.response?.data?.message ?? "Upload failed. Please try again.");
    },
  });

  const handleFile = (file: File) => {
    if (!file.type.includes("pdf")) {
      setUploadError("Only PDF files are accepted.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setUploadError("File must be under 50 MB.");
      return;
    }
    setUploadError(null);
    mutation.mutate(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // reset so the same file can be re-selected after an error
    e.target.value = "";
  };

  const busy = mutation.isPending;

  return (
    <div className="mb-6">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !busy && fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${dragging ? "border-primary-400 bg-primary-50" : "border-gray-200 hover:border-primary-300 hover:bg-gray-50"}
          ${busy ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={onFileChange}
        />
        <Upload className="h-8 w-8 text-gray-400 mx-auto mb-3" />
        {busy ? (
          <div className="space-y-2">
            <p className="text-sm text-gray-600">Uploading…</p>
            {progress !== null && (
              <div className="w-48 mx-auto bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-primary-600 h-1.5 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
            <p className="text-xs text-gray-400">{progress ?? 0}%</p>
          </div>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">Drop a PDF here or click to browse</p>
            <p className="text-xs text-gray-400 mt-1">PDF only · Max 50 MB</p>
          </>
        )}
      </div>
      {uploadError && (
        <div className="flex items-center gap-2 mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {uploadError}
        </div>
      )}
    </div>
  );
}

// ── Document row ─────────────────────────────────────────────────────────────

function DocumentRow({
  doc,
  onDelete,
}: {
  doc: DocumentSummary;
  onDelete: (id: string) => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDeleteClick = () => {
    if (confirmDelete) {
      onDelete(doc.id);
    } else {
      setConfirmDelete(true);
      // auto-reset confirm state after 3 seconds
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  };

  const uploadedDate = new Date(doc.createdAt).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <div className="flex items-start gap-4 p-4 hover:bg-gray-50 transition-colors rounded-lg group">
      <div className="p-2 rounded-lg bg-blue-50 flex-shrink-0">
        <FileText className="h-5 w-5 text-blue-600" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {doc.caseName ?? doc.title ?? doc.originalFilename}
          </p>
          <StatusBadge status={doc.status} />
        </div>
        <p className="text-xs text-gray-500 truncate">{doc.originalFilename}</p>
        <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
          {doc.court && <span>{doc.court}</span>}
          {doc.caseYear && <span>{doc.caseYear}</span>}
          {doc.pageCount != null && <span>{doc.pageCount} pages</span>}
          {doc.chunkCount != null && <span>{doc.chunkCount} chunks</span>}
          <span>{uploadedDate}</span>
        </div>
        {doc.status === "FAILED" && doc.errorMessage && (
          <p className="text-xs text-red-600 mt-1 truncate">
            Error: {doc.errorMessage}
          </p>
        )}
      </div>

      <button
        onClick={handleDeleteClick}
        title={confirmDelete ? "Click again to confirm delete" : "Delete document"}
        className={`flex-shrink-0 p-1.5 rounded-lg transition-colors opacity-0 group-hover:opacity-100
          ${confirmDelete
            ? "bg-red-100 text-red-700 opacity-100"
            : "text-gray-400 hover:text-red-600 hover:bg-red-50"}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
  }, [router]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsApi.list(0, 100).then((r) => r.data),
    // Poll every 5 seconds while any document is PROCESSING or UPLOADED
    refetchInterval: (query) => {
      const docs = query.state.data?.content ?? [];
      const needsPoll = docs.some(
        (d) => d.status === "PROCESSING" || d.status === "UPLOADED"
      );
      return needsPoll ? 5000 : false;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  const docs = data?.content ?? [];
  const readyCount = docs.filter((d) => d.status === "READY").length;
  const processingCount = docs.filter(
    (d) => d.status === "PROCESSING" || d.status === "UPLOADED"
  ).length;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-serif font-bold text-gray-900 mb-1">
              Document Library
            </h1>
            <p className="text-sm text-gray-500">
              {docs.length === 0
                ? "No documents yet — upload a PDF to get started"
                : `${docs.length} document${docs.length !== 1 ? "s" : ""} · ${readyCount} ready${processingCount > 0 ? ` · ${processingCount} processing` : ""}`}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            title="Refresh"
            className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {/* Upload area */}
        <UploadArea
          onUploadComplete={() =>
            queryClient.invalidateQueries({ queryKey: ["documents"] })
          }
        />

        {/* Document list */}
        <div className="card divide-y divide-gray-100">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              <span className="text-sm">Loading documents…</span>
            </div>
          )}

          {isError && (
            <div className="flex items-center gap-2 p-6 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              Failed to load documents.{" "}
              <button
                onClick={() => refetch()}
                className="underline hover:no-underline"
              >
                Retry
              </button>
            </div>
          )}

          {!isLoading && !isError && docs.length === 0 && (
            <div className="py-16 text-center">
              <FileText className="h-10 w-10 text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">
                No documents in your library yet.
              </p>
              <p className="text-xs text-gray-300 mt-1">
                Upload a PDF judgment above to begin.
              </p>
            </div>
          )}

          {docs.map((doc) => (
            <DocumentRow
              key={doc.id}
              doc={doc}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>

        {/* Processing notice */}
        {processingCount > 0 && (
          <p className="text-xs text-blue-600 text-center mt-4">
            <Loader2 className="inline h-3 w-3 animate-spin mr-1" />
            {processingCount} document{processingCount !== 1 ? "s are" : " is"} being processed
            — this page refreshes automatically every 5 seconds.
          </p>
        )}
      </div>
    </AppShell>
  );
}
