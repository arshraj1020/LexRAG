"""
Legal-Aware Document Chunker

Splits documents at legal structure boundaries (Facts, Issues, Arguments,
Analysis, Decision, etc.) before falling back to paragraph-level splits.

Each chunk carries stable citation metadata:
    citation_id: DOC_{doc_short_id}_P{page}_PAR{para_idx}

This is NOT a naive character-count splitter.
"""

import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional
from ..core.settings import get_settings
from .extraction import ExtractedBlock

logger = logging.getLogger(__name__)
settings = get_settings()


# Legal section header patterns (Indian courts common headings)
_LEGAL_SECTION_PATTERNS = [
    r"^\s*(?:\d+\.\s+)?(?:FACTS|BACKGROUND|BRIEF FACTS)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:ISSUES?|QUESTIONS? OF LAW)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:ARGUMENTS?|SUBMISSIONS?|CONTENTIONS?)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:EVIDENCE|EVIDENCE ON RECORD)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:ANALYSIS|REASONING|DISCUSSION)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:LEGAL (?:PROVISIONS?|FRAMEWORK))\s*$",
    r"^\s*(?:\d+\.\s+)?(?:PRECEDENTS?|AUTHORITIES|CASE LAW)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:DECISION|CONCLUSION|FINDINGS?|ORDER|JUDGMENT|HELD)\s*$",
    r"^\s*(?:\d+\.\s+)?(?:RELIEF|RELIEFS? GRANTED|DISPOSAL)\s*$",
]

_SECTION_RE = re.compile("|".join(_LEGAL_SECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


@dataclass
class DocumentChunk:
    """One chunk ready to be embedded and stored in pgvector."""
    document_id: str
    chunk_index: int
    page_number: Optional[int]
    paragraph_number: Optional[int]
    section: Optional[str]
    text: str
    citation_id: str
    # Denormalised for fast search without joins
    case_name: Optional[str] = None
    court: Optional[str] = None
    case_year: Optional[str] = None


def chunk_document(
    document_id: str,
    blocks: list[ExtractedBlock],
    case_name: Optional[str] = None,
    court: Optional[str] = None,
    case_year: Optional[str] = None,
) -> list[DocumentChunk]:
    """
    Convert extracted PDF blocks into overlapping, citation-tagged chunks.

    Strategy:
    1. Detect legal section headers to label chunks with their section name.
    2. Merge small blocks into target chunk size with overlap.
    3. Assign stable citation IDs.
    """
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap
    doc_short = _short_doc_id(document_id)

    chunks: list[DocumentChunk] = []
    current_section: Optional[str] = None
    buffer = []       # list of (page, para_idx, text)
    buffer_len = 0
    chunk_index = 0
    para_counter = 0  # global paragraph counter for citation IDs

    def flush_buffer():
        nonlocal chunk_index
        if not buffer:
            return
        merged_text = " ".join(t for _, _, t in buffer)
        first_page = buffer[0][0]
        first_para = buffer[0][1]
        citation_id = f"DOC_{doc_short}_P{first_page}_PAR{first_para}"
        chunks.append(DocumentChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            page_number=first_page,
            paragraph_number=first_para,
            section=current_section,
            text=merged_text,
            citation_id=citation_id,
            case_name=case_name,
            court=court,
            case_year=case_year,
        ))
        chunk_index += 1

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        para_counter += 1

        # Detect legal section header
        if _SECTION_RE.match(text) and len(text) < 120:
            flush_buffer()
            buffer = []
            buffer_len = 0
            current_section = text.strip()
            continue

        words = text.split()
        word_count = len(words)

        # If adding this block would exceed chunk size, flush first
        if buffer_len + word_count > chunk_size and buffer:
            flush_buffer()
            # Overlap: keep last `overlap` words in buffer
            overlap_text = " ".join(
                t for _, _, t in buffer
            )[-overlap * 6:]  # rough char estimate
            buffer = [(block.page_number, para_counter, overlap_text)] if overlap_text else []
            buffer_len = len(overlap_text.split()) if overlap_text else 0

        buffer.append((block.page_number, para_counter, text))
        buffer_len += word_count

    flush_buffer()

    logger.info(
        "Chunked document %s into %d chunks across sections",
        document_id, len(chunks)
    )
    return chunks


def _short_doc_id(document_id: str) -> str:
    """Produce a short stable identifier from a UUID for citation IDs."""
    return hashlib.sha256(document_id.encode()).hexdigest()[:8].upper()
