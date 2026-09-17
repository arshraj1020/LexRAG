import Link from "next/link";
import { Scale, FileText, Search, BookOpen, History, ArrowRight } from "lucide-react";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-900 to-primary-800 text-white">
      {/* Header */}
      <header className="border-b border-white/10 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Scale className="h-6 w-6 text-legal-gold" />
          <span className="text-xl font-serif font-bold">LexRAG</span>
        </div>
        <nav className="flex gap-4">
          <Link href="/login"
            className="px-4 py-2 text-white/80 hover:text-white text-sm font-medium transition-colors">
            Sign In
          </Link>
          <Link href="/register"
            className="px-4 py-2 bg-legal-gold text-primary-900 rounded-lg text-sm font-semibold
                       hover:bg-yellow-400 transition-colors">
            Get Started
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="px-8 py-24 text-center max-w-4xl mx-auto">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-sm mb-8">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          100% local inference — no API keys required
        </div>

        <h1 className="text-5xl font-serif font-bold mb-6 leading-tight">
          AI Legal Research<br />
          <span className="text-legal-gold">Grounded in Citations</span>
        </h1>

        <p className="text-lg text-white/70 mb-10 max-w-2xl mx-auto">
          Upload legal judgments. Ask research questions. Get citation-verified answers
          powered by local LLMs and hybrid retrieval — without fabrication.
        </p>

        <div className="flex gap-4 justify-center">
          <Link href="/register" className="btn-primary bg-legal-gold text-primary-900
            hover:bg-yellow-400 px-6 py-3 text-base">
            Start Researching <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/login" className="btn-secondary border-white/30 text-white
            hover:bg-white/10 px-6 py-3 text-base">
            Sign In
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="px-8 py-16 max-w-5xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((f) => (
            <div key={f.title} className="card bg-white/5 border-white/10 p-6">
              <div className="mb-4 inline-flex p-2 rounded-lg bg-white/10">
                <f.icon className="h-5 w-5 text-legal-gold" />
              </div>
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-white/60">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <footer className="px-8 py-6 border-t border-white/10 text-center text-xs text-white/40">
        LexRAG is a research assistance tool. Generated information should not be treated as legal advice.
        Always verify primary sources independently.
      </footer>
    </main>
  );
}

const features = [
  {
    icon: FileText,
    title: "Legal Document Ingestion",
    description: "Upload PDF judgments. Our pipeline extracts text, detects structure, and creates legal-aware chunks.",
  },
  {
    icon: Search,
    title: "Hybrid Retrieval + Reranking",
    description: "Dense vector search + BM25 keyword search combined, then neural reranking for maximum precision.",
  },
  {
    icon: BookOpen,
    title: "Citation-Grounded Answers",
    description: "Every claim is tied to a specific page and paragraph. Invalid citations are automatically flagged.",
  },
  {
    icon: Scale,
    title: "Case Comparison",
    description: "Compare multiple judgments side-by-side on facts, reasoning, precedents, and outcome.",
  },
  {
    icon: History,
    title: "Precedent Search",
    description: "Find judgments discussing specific legal grounds across all uploaded documents.",
  },
  {
    icon: FileText,
    title: "Research Briefs",
    description: "Generate structured research briefs with key authorities and conflicting interpretations.",
  },
];
