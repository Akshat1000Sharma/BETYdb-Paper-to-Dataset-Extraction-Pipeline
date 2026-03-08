from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    page_number: int
    text: str


# Extract text from PDF
def extract_text(pdf_path: str | Path) -> list[PageContent]:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = _try_pymupdf(pdf_path)
    if not pages:
        logger.warning("PyMuPDF returned no text, so falling back to pdfplumber.")
        pages = _try_pdfplumber(pdf_path)

    logger.info("Extracted %d pages from '%s'.", len(pages), pdf_path.name)
    return pages


# PyMuPDF backend
def _try_pymupdf(pdf_path: Path) -> list[PageContent]:
    try:
        import fitz

        pages: list[PageContent] = []
        with fitz.open(str(pdf_path)) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if text.strip():
                    pages.append(PageContent(page_number=i, text=text))
        return pages
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed.")
        return []
    except Exception as exc:
        logger.error("PyMuPDF error: %s", exc)
        return []


# pdfplumber backend
def _try_pdfplumber(pdf_path: Path) -> list[PageContent]:
    try:
        import pdfplumber

        pages: list[PageContent] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(PageContent(page_number=i, text=text))
        return pages
    except ImportError:
        logger.error("pdfplumber not installed.  Install it with: pip install pdfplumber")
        return []
    except Exception as exc:
        logger.error("pdfplumber error: %s", exc)
        return []
