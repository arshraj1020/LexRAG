"""
Document Ingestion Pipeline — End-to-End

PDF → Text Extraction → Metadata → Chunking → Embeddings → pgvector

This is the core pipeline that transforms a raw PDF into searchable
embedded chunks stored in PostgreSQL with pgvector.
"""

import logging
import os
import asyncio
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .extraction import extract_pdf
from .metadata import extract_legal_metadata
from .chunking import chunk_document
from ..core.embedder import embed_texts

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    document_id: str
    success: bool
    chunk_count: int = 0
    page_count: int = 0
    metadata: Optional[dict] = None
    error: Optional[str] = None


async def ingest_document(
    db: AsyncSession,
    document_id: str,
    file_path: str,
) -> IngestionResult:
    """
    Full ingestion pipeline for a single PDF document.

    Runs synchronous CPU-bound steps (PDF extraction, embedding) in
    a thread pool to avoid blocking the async event loop.
    """
    logger.info("Starting ingestion for document %s", document_id)

    if not os.path.exists(file_path):
        return IngestionResult(document_id, success=False, error=f"File not found: {file_path}")

    try:
        # ── Step 1: PDF Extraction (CPU-bound → thread pool) ──────────
        loop = asyncio.get_running_loop()
        extracted = await loop.run_in_executor(
            None, extract_pdf, file_path
        )
        logger.info("Extracted %d blocks from %d pages", len(extracted.blocks), extracted.page_count)

        # ── Step 2: Legal Metadata Extraction ─────────────────────────
        meta = await loop.run_in_executor(
            None, extract_legal_metadata, extracted.full_text, extracted.page_count
        )

        # ── Step 3: Legal-Aware Chunking ──────────────────────────────
        chunks = chunk_document(
            document_id=document_id,
            blocks=extracted.blocks,
            case_name=meta.case_name,
            court=meta.court,
            case_year=meta.case_year,
        )
        logger.info("Created %d chunks", len(chunks))

        if not chunks:
            return IngestionResult(
                document_id, success=False,
                error="No text chunks could be created from this document"
            )

        # ── Step 4: Embedding Generation (CPU-bound → thread pool) ────
        texts = [c.text for c in chunks]
        embeddings = await loop.run_in_executor(
            None, embed_texts, texts
        )

        # ── Step 5: Store in PostgreSQL + pgvector ────────────────────
        await _store_chunks(db, chunks, embeddings)
        await _update_document_metadata(db, document_id, meta, len(chunks), extracted.page_count)
        await db.commit()

        logger.info("Ingestion complete for document %s: %d chunks", document_id, len(chunks))
        return IngestionResult(
            document_id=document_id,
            success=True,
            chunk_count=len(chunks),
            page_count=extracted.page_count,
            metadata={
                "case_name": meta.case_name,
                "court": meta.court,
                "jurisdiction": meta.jurisdiction,
                "case_number": meta.case_number,
                "case_year": meta.case_year,
                "judges": meta.judges,
                "document_type": meta.document_type,
                "language": meta.language,
            },
        )

    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        await db.rollback()
        return IngestionResult(document_id, success=False, error=str(exc))


async def _store_chunks(db: AsyncSession, chunks, embeddings: list[list[float]]):
    """Batch-insert chunks with their embeddings into document_chunks."""
    for chunk, embedding in zip(chunks, embeddings):
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        sql = text("""
            INSERT INTO document_chunks
                (document_id, chunk_index, page_number, paragraph_number,
                 section, text, citation_id, case_name, court, case_year, embedding)
            VALUES
                (:document_id, :chunk_index, :page_number, :paragraph_number,
                 :section, :text, :citation_id, :case_name, :court, :case_year,
                 :embedding::vector)
            ON CONFLICT (citation_id) DO UPDATE
                SET text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding
        """)
        await db.execute(sql, {
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "paragraph_number": chunk.paragraph_number,
            "section": chunk.section,
            "text": chunk.text,
            "citation_id": chunk.citation_id,
            "case_name": chunk.case_name,
            "court": chunk.court,
            "case_year": chunk.case_year,
            "embedding": embedding_str,
        })


async def _update_document_metadata(db: AsyncSession, document_id: str, meta, chunk_count: int, page_count: int):
    """Update document record with extracted metadata and processing results."""
    sql = text("""
        UPDATE documents SET
            case_name = :case_name,
            court = :court,
            jurisdiction = :jurisdiction,
            case_number = :case_number,
            case_year = :case_year,
            judges = :judges,
            document_type = :document_type,
            language = :language,
            page_count = :page_count,
            chunk_count = :chunk_count,
            status = 'READY',
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = :document_id::uuid
    """)
    await db.execute(sql, {
        "document_id": document_id,
        "case_name": meta.case_name,
        "court": meta.court,
        "jurisdiction": meta.jurisdiction,
        "case_number": meta.case_number,
        "case_year": meta.case_year,
        "judges": meta.judges,
        "document_type": meta.document_type,
        "language": meta.language,
        "page_count": page_count,
        "chunk_count": chunk_count,
    })
