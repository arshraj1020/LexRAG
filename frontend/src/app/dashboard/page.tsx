"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FileText, Search, ChevronRight } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { getStoredUser, isAuthenticated } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
  }, [router]);

  const user = getStoredUser();

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-serif font-bold text-gray-900 mb-1">
          Welcome{user?.fullName ? `, ${user.fullName.split(" ")[0]}` : ""}
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          LexRAG — AI legal research with citation verification
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link href="/documents"
            className="card p-6 hover:shadow-md transition-shadow group flex items-start gap-4">
            <div className="p-2 rounded-lg bg-blue-50 group-hover:bg-blue-100 transition-colors">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="font-semibold text-gray-900 mb-1">Document Library</h2>
              <p className="text-sm text-gray-500">
                Upload and manage legal judgments. Documents are processed and
                indexed for retrieval automatically.
              </p>
            </div>
            <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0 mt-1
                                     group-hover:text-gray-600 transition-colors" />
          </Link>

          <Link href="/research"
            className="card p-6 hover:shadow-md transition-shadow group flex items-start gap-4">
            <div className="p-2 rounded-lg bg-green-50 group-hover:bg-green-100 transition-colors">
              <Search className="h-5 w-5 text-green-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="font-semibold text-gray-900 mb-1">Legal Research</h2>
              <p className="text-sm text-gray-500">
                Ask research questions. Get citation-grounded answers from your
                documents via hybrid retrieval + reranking.
              </p>
            </div>
            <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0 mt-1
                                     group-hover:text-gray-600 transition-colors" />
          </Link>
        </div>

        {/* Pipeline info */}
        <div className="mt-8 card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">RAG Pipeline</h3>
          <div className="flex items-center gap-2 flex-wrap text-xs text-gray-500">
            {[
              "PDF Ingestion",
              "→",
              "Legal-Aware Chunking",
              "→",
              "all-MiniLM Embeddings",
              "→",
              "pgvector (HNSW)",
              "→",
              "Hybrid Retrieval (RRF)",
              "→",
              "Cross-Encoder Reranking",
              "→",
              "Mistral 7B (Ollama)",
              "→",
              "Citation Verification",
            ].map((step, i) => (
              <span
                key={i}
                className={step === "→" ? "text-gray-300" : "font-medium text-gray-700"}
              >
                {step}
              </span>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            100% local inference — no external APIs or API keys required.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
