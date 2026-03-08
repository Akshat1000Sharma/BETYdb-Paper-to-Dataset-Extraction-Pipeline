from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pipeline.pdf_parser import PageContent

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    chunk_id: int
    text: str
    page_numbers: list[int] = field(default_factory=list)


# Chunk pages
def chunk_pages(
    pages: list[PageContent],
    chunk_size: int = 3000,
    overlap: int = 300,
) -> list[TextChunk]:
    full_text = ""
    page_markers: list[tuple[int, int]] = []

    for page in pages:
        page_markers.append((len(full_text), page.page_number))
        full_text += page.text + "\n"

    if not full_text.strip():
        logger.warning("No text to chunk.")
        return []

    def pages_for_span(start: int, end: int) -> list[int]:
        result = set()
        for i, (offset, pnum) in enumerate(page_markers):
            next_offset = page_markers[i + 1][0] if i + 1 < len(page_markers) else len(full_text)
            if offset < end and next_offset > start:
                result.add(pnum)
        return sorted(result)

    chunks: list[TextChunk] = []
    pos = 0
    chunk_id = 0

    while pos < len(full_text):
        end = pos + chunk_size
        chunk_text = full_text[pos:end]
        pnums = pages_for_span(pos, min(end, len(full_text)))
        chunks.append(TextChunk(chunk_id=chunk_id, text=chunk_text, page_numbers=pnums))
        chunk_id += 1
        pos += chunk_size - overlap

    logger.info("Produced %d chunks (size=%d, overlap=%d).", len(chunks), chunk_size, overlap)
    return chunks
