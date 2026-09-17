"""
Legal metadata extraction from PDF text.

Extracts metadata using pattern matching on the document header.
Never fabricates values — returns None for fields that cannot be found.

Extracted fields:
    case_name, court, jurisdiction, case_number, date, year,
    judges, document_type, language, page_count
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


@dataclass
class LegalMetadata:
    case_name: Optional[str] = None
    court: Optional[str] = None
    jurisdiction: Optional[str] = None
    case_number: Optional[str] = None
    case_date: Optional[str] = None
    case_year: Optional[str] = None
    judges: Optional[str] = None
    document_type: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None


# ── Pattern library ───────────────────────────────────────────

_COURT_PATTERNS = [
    r"(?:IN THE\s+)?(SUPREME COURT OF (?:INDIA|[A-Z\s]+))",
    r"(?:IN THE\s+)?(HIGH COURT OF (?:JUDICATURE AT |)[A-Z\s]+)",
    r"(?:IN THE\s+)?(NATIONAL COMPANY LAW TRIBUNAL[,\s]*[A-Z\s]*)",
    r"(?:IN THE\s+)?(DISTRICT COURT[,\s]*[A-Z\s]*)",
    r"(?:IN THE\s+)?(SESSIONS COURT[,\s]*[A-Z\s]*)",
    r"(?:BEFORE\s+)?(HON(?:'BLE|OURABLE)\s+[A-Z][A-Z\s]+COURT)",
]

_CASE_NUMBER_PATTERNS = [
    r"\b(?:W\.P\.\(C\)|W\.P\.|WP|Criminal Appeal|Crl\.A\.|C\.A\.|SLP|Civil Appeal|CWP)"
    r"\s*(?:No\.?|NUMBER)?\s*[\d/]+(?:\s*/\s*\d{4})?",
    r"\b(?:Petition|Appeal|Suit|Case)\s+No\.?\s*[\d/]+(?:\s*/\s*\d{4})?",
]

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December),?\s+\d{4})\b",
    re.IGNORECASE,
)

_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")

_JUDGE_PATTERNS = [
    r"(?:BEFORE|CORAM)[:\s]+(?:HON(?:'BLE|OURABLE)\.?\s+)?([A-Z][A-Z\s,\.]+(?:J\.|JJ\.|C\.J\.))",
    r"(?:JUSTICE|HON(?:'BLE|OURABLE)\.?\s+JUSTICE)\s+([A-Z][A-Z\s,\.]+)",
]

_DOC_TYPE_KEYWORDS = {
    "judgment": ["JUDGMENT", "JUDGEMENT", "ORDER", "DECIDED"],
    "opinion": ["ADVISORY OPINION"],
    "order": ["ORDER", "DIRECTIONS"],
}


def extract_legal_metadata(text: str, page_count: int) -> LegalMetadata:
    """
    Extract legal metadata from raw document text.

    Uses only the first 3000 characters (document header) for efficiency.
    Never fabricates values.
    """
    header = text[:3000].upper()
    meta = LegalMetadata(page_count=page_count)

    meta.court = _extract_first_match(header, _COURT_PATTERNS)
    meta.case_number = _extract_first_match(text[:2000], _CASE_NUMBER_PATTERNS)

    date_match = _DATE_PATTERN.search(text[:3000])
    if date_match:
        meta.case_date = date_match.group(1)

    year_match = _YEAR_PATTERN.search(text[:1000])
    if year_match:
        meta.case_year = year_match.group(1)

    meta.judges = _extract_first_match(text[:3000], _JUDGE_PATTERNS)

    meta.document_type = _detect_document_type(header)

    try:
        meta.language = detect(text[:2000])
    except LangDetectException:
        meta.language = "unknown"

    # Case name heuristic: often the first substantial line after court header
    meta.case_name = _extract_case_name(text[:2000])

    logger.debug("Extracted metadata: %s", meta)
    return meta


def _extract_first_match(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip() if match.lastindex else match.group(0).strip()
            return _title_case(value)
    return None


def _detect_document_type(header: str) -> Optional[str]:
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        if any(kw in header for kw in keywords):
            return doc_type
    return None


def _extract_case_name(text: str) -> Optional[str]:
    """
    Case names often follow the pattern: PARTY_A vs./v. PARTY_B
    """
    pattern = r"([A-Z][A-Za-z\s\.]+)\s+(?:Vs?\.?|VERSUS)\s+([A-Z][A-Za-z\s\.]+)"
    match = re.search(pattern, text[:1500])
    if match:
        name = f"{match.group(1).strip()} v. {match.group(2).strip()}"
        return name[:500]  # enforce column limit
    return None


def _title_case(text: str) -> str:
    return text.strip().title()
