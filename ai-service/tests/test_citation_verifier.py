"""
Citation verifier unit tests — uses async mocked DB sessions.

Verifies: valid citations pass, missing IDs fail, page/paragraph mismatch flagged.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.citations.citation_verifier import verify_citations, VerifiedCitation


def _mock_db_row(
    citation_id: str,
    page: int,
    paragraph: int,
    case_name: str = "Test v. Test",
    court: str = "High Court",
    text: str = "Chunk text here.",
):
    row = MagicMock()
    row.citation_id = citation_id
    row.page_number = page
    row.paragraph_number = paragraph
    row.case_name = case_name
    row.court = court
    row.text = text
    return row


def _make_db(row_or_none):
    """Return a mocked AsyncSession that returns row_or_none for any execute."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = row_or_none
    db.execute = AsyncMock(return_value=result)
    return db


class TestVerifyCitations:
    @pytest.mark.asyncio
    async def test_valid_citation(self):
        citation = {
            "citation_id": "DOC_ABCD1234_P5_PAR10",
            "claim": "The court held that bail may be granted.",
            "page": 5,
            "paragraph": 10,
        }
        row = _mock_db_row("DOC_ABCD1234_P5_PAR10", page=5, paragraph=10)
        db = _make_db(row)

        results = await verify_citations(db, [citation])

        assert len(results) == 1
        v = results[0]
        assert v.is_valid is True
        assert v.validation_errors == []
        assert v.citation_id == "DOC_ABCD1234_P5_PAR10"
        assert v.page == 5
        assert v.paragraph == 10

    @pytest.mark.asyncio
    async def test_missing_citation_id_is_invalid(self):
        citation = {"citation_id": "", "claim": "some claim", "page": 1, "paragraph": 1}
        db = _make_db(None)

        results = await verify_citations(db, [citation])
        v = results[0]
        assert v.is_valid is False
        assert any("Missing" in e for e in v.validation_errors)

    @pytest.mark.asyncio
    async def test_citation_not_in_db_is_invalid(self):
        citation = {
            "citation_id": "DOC_FAKE0000_P1_PAR1",
            "claim": "hallucinated claim",
            "page": 1,
            "paragraph": 1,
        }
        db = _make_db(None)  # DB returns nothing

        results = await verify_citations(db, [citation])
        v = results[0]
        assert v.is_valid is False
        assert any("not exist" in e.lower() for e in v.validation_errors)

    @pytest.mark.asyncio
    async def test_page_mismatch_flagged(self):
        citation = {
            "citation_id": "DOC_ABCD1234_P5_PAR10",
            "claim": "Some claim",
            "page": 99,  # LLM hallucinated page 99; DB has page 5
            "paragraph": 10,
        }
        row = _mock_db_row("DOC_ABCD1234_P5_PAR10", page=5, paragraph=10)
        db = _make_db(row)

        results = await verify_citations(db, [citation])
        v = results[0]
        assert v.is_valid is False
        assert any("mismatch" in e.lower() or "page" in e.lower() for e in v.validation_errors)

    @pytest.mark.asyncio
    async def test_paragraph_mismatch_flagged(self):
        citation = {
            "citation_id": "DOC_ABCD1234_P5_PAR10",
            "claim": "Some claim",
            "page": 5,
            "paragraph": 999,  # wrong paragraph
        }
        row = _mock_db_row("DOC_ABCD1234_P5_PAR10", page=5, paragraph=10)
        db = _make_db(row)

        results = await verify_citations(db, [citation])
        v = results[0]
        assert v.is_valid is False

    @pytest.mark.asyncio
    async def test_empty_citation_list(self):
        db = _make_db(None)
        results = await verify_citations(db, [])
        assert results == []

    @pytest.mark.asyncio
    async def test_chunk_text_returned_for_valid_citation(self):
        citation = {
            "citation_id": "DOC_ABCD1234_P1_PAR1",
            "claim": "claim",
            "page": 1,
            "paragraph": 1,
        }
        row = _mock_db_row(
            "DOC_ABCD1234_P1_PAR1", page=1, paragraph=1,
            text="The court granted bail considering the nature of the offence."
        )
        db = _make_db(row)

        results = await verify_citations(db, [citation])
        v = results[0]
        assert v.chunk_text == "The court granted bail considering the nature of the offence."

    @pytest.mark.asyncio
    async def test_multiple_citations_processed(self):
        valid_row = _mock_db_row("DOC_GOOD0001_P1_PAR1", page=1, paragraph=1)
        # DB returns valid row for first citation, None for second
        db = AsyncMock()
        result_good = MagicMock()
        result_good.fetchone.return_value = valid_row
        result_bad = MagicMock()
        result_bad.fetchone.return_value = None
        db.execute = AsyncMock(side_effect=[result_good, result_bad])

        citations = [
            {"citation_id": "DOC_GOOD0001_P1_PAR1", "claim": "valid", "page": 1, "paragraph": 1},
            {"citation_id": "DOC_BAD00000_P1_PAR1", "claim": "hallucinated", "page": 1, "paragraph": 1},
        ]
        results = await verify_citations(db, citations)
        assert len(results) == 2
        assert results[0].is_valid is True
        assert results[1].is_valid is False
