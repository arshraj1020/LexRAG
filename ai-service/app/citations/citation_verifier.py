"""
Citation Verification Pipeline — Citation-First Generation.

Every citation produced by the LLM is verified against three criteria:
1. Citation ID exists in the database.
2. Page and paragraph numbers match (if provided by LLM).
3. (Optional) Citation belongs to documents owned by the requesting user.
4. (Optional) Citation was present in the retrieved context (hallucination guard).

Invalid citations are flagged — never silently accepted.
This prevents citation hallucination from reaching users.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class VerifiedCitation:
    citation_id: str
    claim: str
    page: Optional[int]
    paragraph: Optional[int]
    case_name: Optional[str]
    court: Optional[str]
    is_valid: bool
    validation_errors: list[str]
    chunk_text: Optional[str] = None  # actual text for user display


async def verify_citations(
    db: AsyncSession,
    citations: list[dict],
    owner_document_ids: Optional[list[str]] = None,
    retrieved_citation_ids: Optional[set[str]] = None,
) -> list[VerifiedCitation]:
    """
    Verify each citation against the database.

    Args:
        db: Async database session.
        citations: List of citation dicts from LLM (each has citation_id, claim, page, paragraph).
        owner_document_ids: If provided, citations must belong to documents in this list.
                            This enforces owner isolation — no cross-user citation access.
        retrieved_citation_ids: If provided, citations must have been in the retrieved context.
                                 This catches hallucinated citations that were never retrieved.

    Returns a VerifiedCitation for each input citation.
    """
    results = []
    for citation in citations:
        verified = await _verify_single(
            db, citation, owner_document_ids, retrieved_citation_ids
        )
        results.append(verified)
    return results


async def _verify_single(
    db: AsyncSession,
    citation: dict,
    owner_document_ids: Optional[list[str]],
    retrieved_citation_ids: Optional[set[str]],
) -> VerifiedCitation:
    citation_id = citation.get("citation_id", "")
    claim = citation.get("claim", "")
    expected_page = citation.get("page")
    expected_para = citation.get("paragraph")
    errors = []

    if not citation_id:
        return VerifiedCitation(
            citation_id="",
            claim=claim,
            page=expected_page,
            paragraph=expected_para,
            case_name=None,
            court=None,
            is_valid=False,
            validation_errors=["Missing citation_id"],
        )

    # ── Guard 1: Citation must have been in the retrieved context ──────────
    # This catches hallucinations where the LLM invented a citation_id that
    # was never returned by the retrieval pipeline.
    if retrieved_citation_ids is not None and citation_id not in retrieved_citation_ids:
        logger.warning(
            "Hallucinated citation detected: '%s' was not in retrieved context", citation_id
        )
        return VerifiedCitation(
            citation_id=citation_id,
            claim=claim,
            page=expected_page,
            paragraph=expected_para,
            case_name=None,
            court=None,
            is_valid=False,
            validation_errors=[
                f"Citation '{citation_id}' was not retrieved for this query "
                "(possible hallucination)"
            ],
        )

    # ── Guard 2: Lookup citation in database ───────────────────────────────
    sql = text("""
        SELECT
            dc.citation_id,
            dc.page_number,
            dc.paragraph_number,
            dc.text,
            dc.case_name,
            dc.court,
            dc.document_id::text AS document_id
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.citation_id = :citation_id
        LIMIT 1
    """)

    result = await db.execute(sql, {"citation_id": citation_id})
    row = result.fetchone()

    if row is None:
        return VerifiedCitation(
            citation_id=citation_id,
            claim=claim,
            page=expected_page,
            paragraph=expected_para,
            case_name=None,
            court=None,
            is_valid=False,
            validation_errors=[f"Citation '{citation_id}' does not exist in the database"],
        )

    # ── Guard 3: Owner isolation — citation must belong to user's documents ─
    # Prevents cross-user citation access (IDOR via LLM hallucination).
    if owner_document_ids is not None and row.document_id not in owner_document_ids:
        logger.warning(
            "IDOR attempt via citation: '%s' belongs to document '%s' not in owner's set",
            citation_id, row.document_id,
        )
        return VerifiedCitation(
            citation_id=citation_id,
            claim=claim,
            page=expected_page,
            paragraph=expected_para,
            case_name=None,
            court=None,
            is_valid=False,
            validation_errors=[
                f"Citation '{citation_id}' does not belong to your documents"
            ],
        )

    # ── Guard 4: Page/paragraph match ─────────────────────────────────────
    if expected_page is not None and row.page_number != expected_page:
        errors.append(
            f"Page mismatch: LLM claimed page {expected_page}, "
            f"database has page {row.page_number}"
        )

    if expected_para is not None and row.paragraph_number != expected_para:
        errors.append(
            f"Paragraph mismatch: LLM claimed para {expected_para}, "
            f"database has para {row.paragraph_number}"
        )

    return VerifiedCitation(
        citation_id=citation_id,
        claim=claim,
        page=row.page_number,
        paragraph=row.paragraph_number,
        case_name=row.case_name,
        court=row.court,
        is_valid=len(errors) == 0,
        validation_errors=errors,
        chunk_text=row.text,
    )
