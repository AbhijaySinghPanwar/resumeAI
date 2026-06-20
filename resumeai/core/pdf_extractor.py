"""
pdf_extractor.py — PDF text extraction with artifact logging.

Supports pdfplumber (primary) with PyPDF2 fallback.
Returns raw lines exactly as extracted — normalization happens downstream.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union


@dataclass
class ExtractionResult:
    raw_lines: List[str]
    page_count: int
    extractor_used: str
    warnings: List[str] = field(default_factory=list)
    global_links: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and len(self.raw_lines) > 0


def extract_text_from_pdf(source: Union[str, Path, bytes]) -> ExtractionResult:
    """
    Extract raw text lines from a PDF file.

    Args:
        source: File path (str or Path) or raw bytes.

    Returns:
        ExtractionResult with raw lines and extraction metadata.
    """
    # Try pdfplumber first (better layout preservation)
    try:
        import pdfplumber
        return _extract_pdfplumber(source)
    except ImportError:
        pass
    except Exception as e:
        # Fall through to PyPDF2
        warnings = [f"pdfplumber failed: {e}"]
        try:
            result = _extract_pypdf2(source)
            result.warnings = warnings + result.warnings
            return result
        except Exception as e2:
            return ExtractionResult(
                raw_lines=[],
                page_count=0,
                extractor_used="none",
                error=f"All extractors failed. pdfplumber: {e}. PyPDF2: {e2}",
            )

    # pdfplumber not imported, try PyPDF2
    try:
        return _extract_pypdf2(source)
    except Exception as e:
        return ExtractionResult(
            raw_lines=[],
            page_count=0,
            extractor_used="none",
            error=str(e),
        )


def extract_text_from_string(text: str) -> ExtractionResult:
    """
    Wrap a plain text string as an ExtractionResult.
    Used for testing and non-PDF inputs.
    """
    lines = text.splitlines()
    return ExtractionResult(
        raw_lines=lines,
        page_count=1,
        extractor_used="plaintext",
    )


def _extract_pdfplumber(source: Union[str, Path, bytes]) -> ExtractionResult:
    import pdfplumber

    if isinstance(source, bytes):
        ctx = pdfplumber.open(io.BytesIO(source))
    else:
        ctx = pdfplumber.open(source)

    all_lines: List[str] = []
    warnings: List[str] = []
    global_links: List[str] = []
    page_count = 0

    with ctx as pdf:
        page_count = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if text is None:
                warnings.append(f"Page {page_num}: extract_text returned None")
                continue
                
            page_lines = text.splitlines()
            
            # Extract hyperlinks and append them to the text stream
            if page.hyperlinks:
                for link in page.hyperlinks:
                    uri = link.get('uri')
                    if uri:
                        global_links.append(f"[{uri}]")
            
            all_lines.extend(page_lines)
            # Add page boundary marker (empty line between pages)
            all_lines.append("")

    return ExtractionResult(
        raw_lines=all_lines,
        page_count=page_count,
        extractor_used="pdfplumber",
        warnings=warnings,
        global_links=global_links,
    )


def _extract_pypdf2(source: Union[str, Path, bytes]) -> ExtractionResult:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        from pypdf import PdfReader  # newer name

    if isinstance(source, bytes):
        reader = PdfReader(io.BytesIO(source))
    else:
        reader = PdfReader(str(source))

    all_lines: List[str] = []
    warnings: List[str] = []
    page_count = len(reader.pages)

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if not text:
            warnings.append(f"Page {page_num}: extract_text returned empty")
            continue
        page_lines = text.splitlines()
        all_lines.extend(page_lines)
        all_lines.append("")

    return ExtractionResult(
        raw_lines=all_lines,
        page_count=page_count,
        extractor_used="pypdf2",
        warnings=warnings,
    )
