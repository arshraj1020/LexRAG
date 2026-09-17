"""
PDF text extraction using PyMuPDF.

Preserves page numbers and paragraph/block structure needed for
accurate citation generation (DOC_{id}_P{page}_PAR{para}).

Detects scanned pages and falls back to Tesseract OCR.
"""

import pymupdf as fitz  # PyMuPDF (use modern import; 'import fitz' is deprecated)
import pytesseract
from PIL import Image
import io
import re
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Threshold: if a page has fewer characters than this, treat it as scanned
SCANNED_PAGE_CHAR_THRESHOLD = 50


@dataclass
class ExtractedBlock:
    """One text block from a PDF page — maps to a paragraph/section."""
    page_number: int        # 1-indexed
    block_index: int        # position within page
    text: str
    is_ocr: bool = False


@dataclass
class ExtractedDocument:
    """Result of full PDF extraction."""
    page_count: int
    blocks: list[ExtractedBlock] = field(default_factory=list)
    full_text: str = ""
    has_ocr_pages: bool = False
    extraction_warnings: list[str] = field(default_factory=list)


def extract_pdf(file_path: str) -> ExtractedDocument:
    """
    Extract all text from a PDF, preserving page/block structure.

    Scanned pages are detected by low text density and processed with
    Tesseract OCR to produce usable text.
    """
    doc = fitz.open(file_path)
    result = ExtractedDocument(page_count=len(doc))
    all_text_parts: list[str] = []

    for page_num_zero in range(len(doc)):
        page = doc[page_num_zero]
        page_number = page_num_zero + 1  # 1-indexed

        # Extract text with block positions
        page_text = page.get_text("text").strip()

        if len(page_text) < SCANNED_PAGE_CHAR_THRESHOLD:
            # Likely a scanned/image page — attempt OCR
            logger.info("Page %d appears scanned — attempting OCR", page_number)
            ocr_text = _ocr_page(page)
            if ocr_text:
                result.has_ocr_pages = True
                block = ExtractedBlock(
                    page_number=page_number,
                    block_index=0,
                    text=_clean_text(ocr_text),
                    is_ocr=True,
                )
                result.blocks.append(block)
                all_text_parts.append(ocr_text)
            else:
                result.extraction_warnings.append(
                    f"Page {page_number}: OCR returned empty text"
                )
        else:
            # Extract individual text blocks (paragraphs)
            blocks_raw = page.get_text("blocks")
            for block_idx, block_data in enumerate(blocks_raw):
                # block_data: (x0, y0, x1, y1, text, block_no, block_type)
                block_type = block_data[6]
                if block_type != 0:  # skip image blocks
                    continue
                text = _clean_text(block_data[4])
                if not text:
                    continue
                result.blocks.append(ExtractedBlock(
                    page_number=page_number,
                    block_index=block_idx,
                    text=text,
                ))
            all_text_parts.append(page_text)

    result.full_text = "\n\n".join(all_text_parts)
    doc.close()
    return result


def _ocr_page(page: fitz.Page, dpi: int = 200) -> str:
    """Render page to image and run Tesseract OCR."""
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="eng")
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def _clean_text(text: str) -> str:
    """Normalise whitespace and remove control characters."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
