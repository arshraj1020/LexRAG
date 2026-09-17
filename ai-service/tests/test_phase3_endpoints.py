"""
Phase 3 endpoint tests — compare, precedents, provision, brief.

Tests cover:
  - Insufficient evidence path (no chunks retrieved → structured field is None)
  - Valid flow: mocked retrieval + LLM returns verified citations
  - Fabricated citation rejection (LLM cites ID not in retrieved set)
  - Provision: 400 when neither 'provision' nor 'provision_query' is supplied
  - ProvisionRequest.effective_provision resolution priority
  - Compare: requires ≥2 document_ids (Pydantic validation)
  - CompareRequest/PrecedentRequest/BriefRequest field acceptance
  - _extract_all_citation_ids: JSON path and regex fallback
  - _confidence_to_float: HIGH/MEDIUM/LOW/unknown mappings

All DB and LLM calls are mocked — no live services required.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError


# ── Model / helper imports ───────────────────────────────────────────────────

from app.api.routes import (
    CompareRequest,
    PrecedentRequest,
    ProvisionRequest,
    BriefRequest,
    _confidence_to_float,
    _extract_all_citation_ids,
    _verified_to_dict,
    _chunk_to_dict,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_chunk(citation_id: str = "DOC_ABCD1234_P1_PAR1", document_id: str = "doc-1"):
    c = MagicMock()
    c.citation_id = citation_id
    c.document_id = document_id
    c.page_number = 1
    c.paragraph_number = 1
    c.section = "Section 1"
    c.text = "Evidence text."
    c.case_name = "Test v. Test"
    c.court = "High Court"
    c.case_year = "2020"
    c.dense_score = 0.9
    c.sparse_score = 0.8
    c.fusion_score = 0.85
    c.rerank_score = 0.92
    return c


def _make_verified(citation_id: str, is_valid: bool = True):
    v = MagicMock()
    v.citation_id = citation_id
    v.claim = "Some claim."
    v.page = 1
    v.paragraph = 1
    v.case_name = "Test v. Test"
    v.court = "High Court"
    v.is_valid = is_valid
    v.validation_errors = [] if is_valid else ["Not in retrieved context"]
    v.chunk_text = "Evidence text." if is_valid else None
    return v


def _make_llm_response(answer: str = '{"precedents": []}', confidence: str = "HIGH",
                        raw_text: str = "", parse_error: bool = False):
    r = MagicMock()
    r.answer = answer
    r.confidence = confidence
    r.raw_text = raw_text or answer
    r.citations = []
    r.parse_error = parse_error
    return r


# ── _confidence_to_float ─────────────────────────────────────────────────────

class TestConfidenceToFloat:
    def test_high(self):
        assert _confidence_to_float("HIGH") == 0.85

    def test_high_lowercase(self):
        assert _confidence_to_float("high") == 0.85

    def test_medium(self):
        assert _confidence_to_float("MEDIUM") == 0.55

    def test_low(self):
        assert _confidence_to_float("LOW") == 0.25

    def test_unknown_returns_none(self):
        assert _confidence_to_float("UNKNOWN") is None

    def test_none_returns_none(self):
        assert _confidence_to_float(None) is None

    def test_empty_string_returns_none(self):
        assert _confidence_to_float("") is None


# ── _extract_all_citation_ids ────────────────────────────────────────────────

class TestExtractAllCitationIds:
    def test_json_path_flat_list(self):
        raw = json.dumps({"citations": ["DOC_ABCD1234_P1_PAR1", "DOC_EFGH5678_P2_PAR3"]})
        result = _extract_all_citation_ids(raw)
        ids = [r["citation_id"] for r in result]
        assert "DOC_ABCD1234_P1_PAR1" in ids
        assert "DOC_EFGH5678_P2_PAR3" in ids

    def test_json_path_nested(self):
        # _collect_citation_ids_recursive looks for "citation_id" dict keys
        # and string items in "citations" / "key_citations" lists.
        raw = json.dumps({
            "cases": [{"citation_id": "DOC_ABCD1234_P3_PAR5"}],
            "findings": {"citations": ["DOC_EFAB5678_P7_PAR2"]},
        })
        result = _extract_all_citation_ids(raw)
        ids = [r["citation_id"] for r in result]
        assert "DOC_ABCD1234_P3_PAR5" in ids
        assert "DOC_EFAB5678_P7_PAR2" in ids

    def test_regex_fallback_on_invalid_json(self):
        # Regex pattern is [A-F0-9]{8} (valid hex chars only).
        # Citation IDs are DOC_{sha256_8chars}_P{page}_PAR{para}
        raw = "Some text DOC_ABCD1234_P1_PAR1 and DOC_EFAB5678_P9_PAR10 embedded."
        result = _extract_all_citation_ids(raw)
        ids = [r["citation_id"] for r in result]
        assert "DOC_ABCD1234_P1_PAR1" in ids
        assert "DOC_EFAB5678_P9_PAR10" in ids

    def test_deduplication(self):
        raw = "DOC_ABCD1234_P1_PAR1 DOC_ABCD1234_P1_PAR1 DOC_ABCD1234_P1_PAR1"
        result = _extract_all_citation_ids(raw)
        assert len(result) == 1

    def test_empty_string_returns_empty(self):
        assert _extract_all_citation_ids("") == []

    def test_no_ids_in_text_returns_empty(self):
        assert _extract_all_citation_ids("no citation IDs here") == []

    def test_returns_dicts_with_none_page_paragraph(self):
        raw = "DOC_ABCD1234_P1_PAR1"
        result = _extract_all_citation_ids(raw)
        assert result[0]["page"] is None
        assert result[0]["paragraph"] is None
        assert result[0]["claim"] == ""

    def test_code_fence_stripped_before_parse(self):
        raw = "```json\n{\"citation_id\": \"DOC_ABCD1234_P1_PAR1\"}\n```"
        result = _extract_all_citation_ids(raw)
        ids = [r["citation_id"] for r in result]
        assert "DOC_ABCD1234_P1_PAR1" in ids


# ── ProvisionRequest.effective_provision ─────────────────────────────────────

class TestProvisionRequest:
    def test_provision_field_used(self):
        r = ProvisionRequest(provision="Section 302 IPC")
        assert r.effective_provision == "Section 302 IPC"

    def test_provision_query_fallback(self):
        r = ProvisionRequest(provision_query="Section 420 IPC")
        assert r.effective_provision == "Section 420 IPC"

    def test_provision_takes_priority_over_provision_query(self):
        r = ProvisionRequest(provision="Section 302", provision_query="Section 420")
        assert r.effective_provision == "Section 302"

    def test_neither_set_returns_empty(self):
        r = ProvisionRequest()
        assert r.effective_provision == ""


# ── CompareRequest validation ─────────────────────────────────────────────────

class TestCompareRequest:
    def test_minimum_two_document_ids(self):
        # Should succeed with 2 doc IDs
        r = CompareRequest(
            question="Compare these cases",
            document_ids=["doc-1", "doc-2"],
        )
        assert len(r.document_ids) == 2

    def test_one_document_id_fails_validation(self):
        with pytest.raises(ValidationError):
            CompareRequest(question="Compare", document_ids=["doc-1"])

    def test_empty_document_ids_fails_validation(self):
        with pytest.raises(ValidationError):
            CompareRequest(question="Compare", document_ids=[])

    def test_eleven_document_ids_fails_validation(self):
        with pytest.raises(ValidationError):
            CompareRequest(
                question="Compare",
                document_ids=[f"doc-{i}" for i in range(11)],
            )

    def test_ten_document_ids_succeeds(self):
        r = CompareRequest(
            question="Compare all",
            document_ids=[f"doc-{i}" for i in range(10)],
        )
        assert len(r.document_ids) == 10

    def test_optional_filter_fields(self):
        r = CompareRequest(
            question="Compare with filters",
            document_ids=["doc-1", "doc-2"],
            court="High Court",
            year_from=2015,
            year_to=2023,
        )
        assert r.court == "High Court"
        assert r.year_from == 2015
        assert r.year_to == 2023


# ── PrecedentRequest validation ───────────────────────────────────────────────

class TestPrecedentRequest:
    def test_basic_fields(self):
        r = PrecedentRequest(query="bail in murder cases")
        assert r.query == "bail in murder cases"
        assert r.document_ids is None
        assert r.top_k is None

    def test_jurisdiction_field_accepted(self):
        r = PrecedentRequest(query="query", jurisdiction="Delhi High Court")
        assert r.jurisdiction == "Delhi High Court"

    def test_top_k_max_25(self):
        with pytest.raises(ValidationError):
            PrecedentRequest(query="q", top_k=26)

    def test_top_k_min_1(self):
        with pytest.raises(ValidationError):
            PrecedentRequest(query="q", top_k=0)

    def test_top_k_25_succeeds(self):
        r = PrecedentRequest(query="q", top_k=25)
        assert r.top_k == 25


# ── BriefRequest validation ───────────────────────────────────────────────────

class TestBriefRequest:
    def test_basic_fields(self):
        r = BriefRequest(research_question="What is the test for contempt?")
        assert r.research_question == "What is the test for contempt?"

    def test_optional_fields(self):
        r = BriefRequest(
            research_question="question",
            jurisdiction="Supreme Court of India",
            document_type="judgment",
            court="Supreme Court",
            year_from=2010,
            year_to=2024,
        )
        assert r.jurisdiction == "Supreme Court of India"
        assert r.document_type == "judgment"


# ── _verified_to_dict ─────────────────────────────────────────────────────────

class TestVerifiedToDict:
    def test_valid_citation_dict(self):
        v = _make_verified("DOC_ABCD1234_P1_PAR1", is_valid=True)
        d = _verified_to_dict(v)
        assert d["citation_id"] == "DOC_ABCD1234_P1_PAR1"
        assert d["is_valid"] is True
        assert d["validation_errors"] == []
        assert d["chunk_text"] == "Evidence text."

    def test_invalid_citation_dict(self):
        v = _make_verified("DOC_FAKE0000_P1_PAR1", is_valid=False)
        d = _verified_to_dict(v)
        assert d["is_valid"] is False
        assert len(d["validation_errors"]) > 0
        assert d["chunk_text"] is None


# ── _chunk_to_dict ────────────────────────────────────────────────────────────

class TestChunkToDict:
    def test_all_fields_present(self):
        c = _make_chunk()
        d = _chunk_to_dict(c)
        for key in ("citation_id", "document_id", "page_number", "paragraph_number",
                    "section", "text", "case_name", "court", "case_year",
                    "dense_score", "sparse_score", "fusion_score", "rerank_score"):
            assert key in d, f"Missing key: {key}"


# ── Endpoint integration tests (heavy mocking) ────────────────────────────────

class TestCompareEndpoint:
    """Test /internal/compare endpoint logic via direct function call with mocks."""

    @pytest.mark.asyncio
    async def test_insufficient_evidence_returns_none_structured(self):
        """When no chunks are retrieved, structured_comparison must be None."""
        from app.api.routes import compare_cases

        mock_db = AsyncMock()
        mock_request = CompareRequest(
            question="Compare the two cases",
            document_ids=["doc-1", "doc-2"],
        )

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.rerank") as mock_rr:
            mock_hs.return_value = []  # No chunks found
            result = await compare_cases(mock_request, mock_db)

        assert result["structured_comparison"] is None
        assert result["verified_citations"] == []
        assert result["invalid_citations"] == []
        assert "INSUFFICIENT_EVIDENCE" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_fabricated_citation_rejected(self):
        """LLM cites DOC_FAKE that was never retrieved → appears in invalid_citations."""
        from app.api.routes import compare_cases

        mock_db = AsyncMock()
        chunk = _make_chunk("DOC_REAL1234_P1_PAR1")
        verified_real = _make_verified("DOC_REAL1234_P1_PAR1", is_valid=True)
        verified_fake = _make_verified("DOC_FAKE0000_P1_PAR1", is_valid=False)
        verified_fake.validation_errors = ["Not in retrieved context"]

        llm_resp = _make_llm_response(
            raw_text='{"citation_ids": ["DOC_REAL1234_P1_PAR1", "DOC_FAKE0000_P1_PAR1"]}'
        )

        mock_request = CompareRequest(
            question="Compare", document_ids=["doc-1", "doc-2"]
        )

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.rerank") as mock_rr, \
             patch("app.api.routes._llm") as mock_llm, \
             patch("app.api.routes.verify_citations", new_callable=AsyncMock) as mock_vc:
            mock_hs.return_value = [chunk]
            mock_rr.return_value = [chunk]
            mock_llm.generate_with_system.return_value = llm_resp
            mock_vc.return_value = [verified_real, verified_fake]

            result = await compare_cases(mock_request, mock_db)

        assert len(result["verified_citations"]) == 1
        assert len(result["invalid_citations"]) == 1
        assert result["invalid_citations"][0]["citation_id"] == "DOC_FAKE0000_P1_PAR1"
        assert not result["invalid_citations"][0]["is_valid"]


class TestPrecedentsEndpoint:
    @pytest.mark.asyncio
    async def test_insufficient_evidence_returns_empty_precedents(self):
        """When no chunks found, precedents list must be empty."""
        from app.api.routes import find_precedents

        mock_db = AsyncMock()
        mock_request = PrecedentRequest(query="bail in murder cases")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq:
            mock_eq.return_value = ["bail in murder cases"]
            mock_hs.return_value = []
            result = await find_precedents(mock_request, mock_db)

        assert result["precedents"] == []
        assert result["verified_citations"] == []
        assert result["retrieved_chunks"] == 0

    @pytest.mark.asyncio
    async def test_precedents_parsed_from_llm_json(self):
        """Precedents list is extracted from the 'precedents' key in LLM JSON."""
        from app.api.routes import find_precedents

        mock_db = AsyncMock()
        chunk = _make_chunk("DOC_ABCD1234_P1_PAR1")
        verified = _make_verified("DOC_ABCD1234_P1_PAR1", is_valid=True)

        precedent_data = {"precedents": [
            {"rank": 1, "citation_id": "DOC_ABCD1234_P1_PAR1",
             "case_name": "State v. Accused", "legal_principle": "Bail principle"}
        ]}
        llm_resp = _make_llm_response(
            answer=json.dumps(precedent_data),
            raw_text=json.dumps(precedent_data),
        )

        mock_request = PrecedentRequest(query="bail principles")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq, \
             patch("app.api.routes.rerank") as mock_rr, \
             patch("app.api.routes._llm") as mock_llm, \
             patch("app.api.routes.verify_citations", new_callable=AsyncMock) as mock_vc:
            mock_eq.return_value = ["bail principles"]
            mock_hs.return_value = [chunk]
            mock_rr.return_value = [chunk]
            mock_llm.generate_with_system.return_value = llm_resp
            mock_vc.return_value = [verified]

            result = await find_precedents(mock_request, mock_db)

        assert len(result["precedents"]) == 1
        assert result["precedents"][0]["case_name"] == "State v. Accused"
        assert result["retrieved_chunks"] == 1


class TestProvisionEndpoint:
    @pytest.mark.asyncio
    async def test_missing_provision_raises_400(self):
        """ProvisionRequest with neither field → effective_provision is empty → 400."""
        from app.api.routes import analyse_provision
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_request = ProvisionRequest()  # neither field set

        with pytest.raises(HTTPException) as exc_info:
            await analyse_provision(mock_request, mock_db)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_insufficient_evidence_returns_null_analysis(self):
        """When no chunks found, structured_analysis must be None."""
        from app.api.routes import analyse_provision

        mock_db = AsyncMock()
        mock_request = ProvisionRequest(provision="Section 302 IPC")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq:
            mock_eq.return_value = ["Section 302 IPC"]
            mock_hs.return_value = []
            result = await analyse_provision(mock_request, mock_db)

        assert result["structured_analysis"] is None
        assert result["verified_citations"] == []
        assert "INSUFFICIENT_EVIDENCE" in result.get("explanation", "")

    @pytest.mark.asyncio
    async def test_provision_query_field_accepted(self):
        """Legacy 'provision_query' field should work via effective_provision."""
        from app.api.routes import analyse_provision

        mock_db = AsyncMock()
        # Use provision_query (legacy field)
        mock_request = ProvisionRequest(provision_query="Article 21 Constitution")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq:
            mock_eq.return_value = ["Article 21 Constitution"]
            mock_hs.return_value = []
            result = await analyse_provision(mock_request, mock_db)

        # Should not raise 400 — effective_provision was "Article 21 Constitution"
        assert result["provision"] == "Article 21 Constitution"

    @pytest.mark.asyncio
    async def test_disclaimer_present_in_response(self):
        """Provision analysis response must include a disclaimer."""
        from app.api.routes import analyse_provision

        mock_db = AsyncMock()
        chunk = _make_chunk()
        verified = _make_verified("DOC_ABCD1234_P1_PAR1", is_valid=True)
        llm_resp = _make_llm_response(answer='{"analysis": "..."}')

        mock_request = ProvisionRequest(provision="Section 302 IPC")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq, \
             patch("app.api.routes.rerank") as mock_rr, \
             patch("app.api.routes._llm") as mock_llm, \
             patch("app.api.routes.verify_citations", new_callable=AsyncMock) as mock_vc:
            mock_eq.return_value = ["Section 302 IPC"]
            mock_hs.return_value = [chunk]
            mock_rr.return_value = [chunk]
            mock_llm.generate_with_system.return_value = llm_resp
            mock_vc.return_value = [verified]

            result = await analyse_provision(mock_request, mock_db)

        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 10


class TestBriefEndpoint:
    @pytest.mark.asyncio
    async def test_insufficient_evidence_returns_null_brief(self):
        """When no chunks found, structured_brief must be None."""
        from app.api.routes import generate_brief

        mock_db = AsyncMock()
        mock_request = BriefRequest(research_question="What is the standard of proof?")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq:
            mock_eq.return_value = ["standard of proof"]
            mock_hs.return_value = []
            result = await generate_brief(mock_request, mock_db)

        assert result["structured_brief"] is None
        assert result["retrieved_chunks"] == 0
        assert "INSUFFICIENT_EVIDENCE" in result.get("explanation", "")

    @pytest.mark.asyncio
    async def test_generation_error_returns_null_brief(self):
        """GENERATION_ERROR from LLM → structured_brief is None, not raw string."""
        from app.api.routes import generate_brief

        mock_db = AsyncMock()
        chunk = _make_chunk()
        llm_resp = _make_llm_response(answer="GENERATION_ERROR", parse_error=True)

        mock_request = BriefRequest(research_question="What is the test?")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq, \
             patch("app.api.routes.rerank") as mock_rr, \
             patch("app.api.routes._llm") as mock_llm, \
             patch("app.api.routes.verify_citations", new_callable=AsyncMock) as mock_vc:
            mock_eq.return_value = ["test"]
            mock_hs.return_value = [chunk]
            mock_rr.return_value = [chunk]
            mock_llm.generate_with_system.return_value = llm_resp
            mock_vc.return_value = []

            result = await generate_brief(mock_request, mock_db)

        assert result["structured_brief"] is None

    @pytest.mark.asyncio
    async def test_citations_split_valid_invalid(self):
        """valid and invalid citations are returned in separate lists."""
        from app.api.routes import generate_brief

        mock_db = AsyncMock()
        chunk = _make_chunk("DOC_REAL1234_P1_PAR1")
        verified_good = _make_verified("DOC_REAL1234_P1_PAR1", is_valid=True)
        verified_bad = _make_verified("DOC_FAKE0000_P1_PAR1", is_valid=False)
        llm_resp = _make_llm_response(
            answer='{"executive_summary": "..."}',
            raw_text="DOC_REAL1234_P1_PAR1 DOC_FAKE0000_P1_PAR1",
        )

        mock_request = BriefRequest(research_question="What is the test for contempt?")

        with patch("app.api.routes.hybrid_search", new_callable=AsyncMock) as mock_hs, \
             patch("app.api.routes.expand_query") as mock_eq, \
             patch("app.api.routes.rerank") as mock_rr, \
             patch("app.api.routes._llm") as mock_llm, \
             patch("app.api.routes.verify_citations", new_callable=AsyncMock) as mock_vc:
            mock_eq.return_value = ["contempt"]
            mock_hs.return_value = [chunk]
            mock_rr.return_value = [chunk]
            mock_llm.generate_with_system.return_value = llm_resp
            mock_vc.return_value = [verified_good, verified_bad]

            result = await generate_brief(mock_request, mock_db)

        assert len(result["verified_citations"]) == 1
        assert len(result["invalid_citations"]) == 1
        assert result["verified_citations"][0]["is_valid"] is True
        assert result["invalid_citations"][0]["is_valid"] is False
