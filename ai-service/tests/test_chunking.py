"""
Legal chunker unit tests — no DB or ML dependencies required.
"""

import pytest
from app.ingestion.chunking import chunk_document


class FakeBlock:
    def __init__(self, text: str, page: int, block_index: int):
        self.text = text
        self.page_number = page
        self.block_index = block_index


def _make_blocks(n: int, page: int = 1) -> list[FakeBlock]:
    return [
        FakeBlock(f"Block {i} with some legal text about section {i}.", page, i)
        for i in range(n)
    ]


def test_chunk_document_produces_chunks():
    doc_id = "test-document-id-1234"
    blocks = _make_blocks(10)
    chunks = chunk_document(document_id=doc_id, blocks=blocks)
    assert len(chunks) > 0


def test_chunk_citation_id_format():
    doc_id = "abcdef12-0000-0000-0000-000000000000"
    blocks = _make_blocks(5)
    chunks = chunk_document(document_id=doc_id, blocks=blocks)
    for chunk in chunks:
        assert chunk.citation_id.startswith("DOC_")
        assert "_P" in chunk.citation_id
        assert "_PAR" in chunk.citation_id


def test_chunk_citation_ids_are_unique():
    doc_id = "abcdef12-0000-0000-0000-000000000000"
    blocks = _make_blocks(20)
    chunks = chunk_document(document_id=doc_id, blocks=blocks)
    ids = [c.citation_id for c in chunks]
    assert len(ids) == len(set(ids)), "Citation IDs must be unique within a document"


def test_empty_blocks_returns_empty():
    chunks = chunk_document(document_id="x", blocks=[])
    assert chunks == []
