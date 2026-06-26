"""Page-aware PDF chunking with pillar hints and table markdown for RAG."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz

from greengag.models.extraction import TextChunk

logger = logging.getLogger("greengag.pdf.chunker")

# Rough token estimate: ~4 chars per token for English prose.
CHARS_PER_TOKEN = 4
TARGET_TOKENS = 800
OVERLAP_TOKENS = 128
TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN

HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\s+)?[A-Z][A-Za-z0-9\s,&\-–—]{2,60}$")
MD_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
PICTURE_OMITTED_RE = re.compile(
    r"^\s*\*{0,2}==>\s*picture\s*\[\d+\s*x\s*\d+\].*?(?:omitted|<==).*?\*{0,2}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PICTURE_TEXT_BLOCK_RE = re.compile(
    r"\*{0,2}-{3,}\s*Start of picture text\s*-{3,}\*{0,2}.*?"
    r"\*{0,2}-{3,}\s*End of picture text\s*-{3,}\*{0,2}",
    re.IGNORECASE | re.DOTALL,
)
BROKEN_TABLE_LINE_RE = re.compile(r"^\|(?:\s*\|)+\s*$")

PILLAR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "environment": (
        "carbon",
        "emission",
        "energy",
        "renewable",
        "water",
        "waste",
        "biodiversity",
        "climate",
        "ghg",
        "net zero",
        "recycl",
        "environment",
    ),
    "social": (
        "employee",
        "worker",
        "safety",
        "community",
        "diversity",
        "human rights",
        "training",
        "health",
        "labour",
        "labor",
        "social",
        "stakeholder",
    ),
    "governance": (
        "board",
        "governance",
        "ethics",
        "compliance",
        "audit",
        "risk",
        "anti-corruption",
        "transparency",
        "policy",
        "whistle",
    ),
}


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _infer_pillar(text: str, heading: str | None) -> str | None:
    hay = f"{heading or ''} {text}".lower()
    scores = {
        pillar: sum(1 for kw in kws if kw in hay)
        for pillar, kws in PILLAR_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None
    tied = [p for p, s in scores.items() if s == scores[best]]
    return tied[0] if len(tied) == 1 else None


def _split_page_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= TARGET_CHARS:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= TARGET_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(para) <= TARGET_CHARS:
            current = para
            continue
        start = 0
        while start < len(para):
            end = min(start + TARGET_CHARS, len(para))
            chunks.append(para[start:end])
            if end >= len(para):
                break
            start = max(end - OVERLAP_CHARS, start + 1)
        current = ""

    if current:
        chunks.append(current)

    overlapped: list[str] = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            overlapped.append(chunk)
            continue
        prev_tail = chunks[i - 1][-OVERLAP_CHARS:]
        overlapped.append(f"{prev_tail}\n{chunk}".strip())
    return overlapped


def _heading_from_layout_page(
    text: str,
    toc_items: list,
    page_num: int,
    fallback: str | None,
) -> str | None:
    for item in toc_items or []:
        if len(item) >= 3 and int(item[2]) == page_num:
            title = str(item[1]).strip()
            if title:
                return title
    for line in text.splitlines():
        match = MD_HEADING_RE.match(line.strip())
        if match:
            return re.sub(r"\*\*", "", match.group(1)).strip()
    return fallback


def _extract_table_rows_from_picture_block(block: str) -> str | None:
    """Recover markdown table rows from pymupdf4llm table-fallback blocks."""
    rows: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or "picture text" in line.lower():
            continue
        if not (line.startswith("|") and line.endswith("|")):
            continue
        if BROKEN_TABLE_LINE_RE.match(line):
            continue
        rows.append(line)
    if len(rows) < 2:
        return None
    return "\n".join(rows)


def _sanitize_layout_markdown(text: str) -> str:
    """Strip pymupdf4llm picture placeholders, <br> tags, and noisy wrappers."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    def _replace_picture_block(match: re.Match[str]) -> str:
        recovered = _extract_table_rows_from_picture_block(match.group(0))
        return f"\n\n{recovered}\n\n" if recovered else ""

    text = PICTURE_TEXT_BLOCK_RE.sub(_replace_picture_block, text)
    text = PICTURE_OMITTED_RE.sub("", text)
    text = re.sub(
        r"^(#{1,6})\s+\*\*(.+?)\*\*\s*$",
        r"\1 \2",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if BROKEN_TABLE_LINE_RE.match(stripped.strip()):
            continue
        if re.fullmatch(r"[-|_\s]+", stripped.strip()):
            continue
        lines.append(stripped)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _merge_page_tables(page: fitz.Page, text: str) -> str:
    """Append native find_tables() markdown when layout missed table structure."""
    parts = [text] if text else []
    for _, table_md in _extract_page_tables(page):
        normalized = table_md.strip()
        if normalized and normalized not in text:
            parts.append(normalized)
    return "\n\n".join(p for p in parts if p).strip()


def _detect_heading(block_text: str) -> str | None:
    first_line = block_text.strip().split("\n", 1)[0].strip()
    if HEADING_RE.match(first_line) and len(first_line) < 80:
        return first_line
    return None


def _chunk_with_layout(pdf_bytes: bytes) -> list[TextChunk]:
    """Layout-aware extraction via pymupdf4llm (bundles pymupdf_layout)."""
    import pymupdf4llm  # noqa: F401 — activates pymupdf.layout on import

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_chunks = pymupdf4llm.to_markdown(
            doc,
            page_chunks=True,
            header=False,
            footer=False,
            force_text=False,
            write_images=False,
            embed_images=False,
        )

        if not isinstance(page_chunks, list):
            raise RuntimeError("Expected page_chunks list from pymupdf4llm.")

        chunks: list[TextChunk] = []
        idx = 0
        current_heading: str | None = None

        for page_chunk in page_chunks:
            raw_text = str(page_chunk.get("text") or "").strip()
            if not raw_text:
                continue

            metadata = page_chunk.get("metadata") or {}
            page_num = int(metadata.get("page_number") or (len(chunks) + 1))
            page = doc[page_num - 1]
            text = _merge_page_tables(page, _sanitize_layout_markdown(raw_text))
            if not text:
                continue

            page_heading = _heading_from_layout_page(
                text,
                page_chunk.get("toc_items") or [],
                page_num,
                current_heading,
            )
            if page_heading:
                # Strip markdown bold/heading markers from section title.
                current_heading = re.sub(r"^\*+|\*+$", "", page_heading).strip()

            for part in _split_page_text(text):
                chunks.append(
                    TextChunk(
                        chunk_index=idx,
                        page=page_num,
                        section_heading=current_heading,
                        pillar_hint=_infer_pillar(part, current_heading),
                        content=part,
                        token_estimate=_estimate_tokens(part),
                    )
                )
                idx += 1

        if not chunks:
            raise RuntimeError("Layout extraction produced no text chunks.")
        return chunks
    finally:
        doc.close()


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _rows_to_markdown(rows: list[list[object | None]]) -> str:
    if not rows:
        return ""
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return ""

    col_count = max(len(row) for row in cleaned)
    padded = [row + [""] * (col_count - len(row)) for row in cleaned]
    header = padded[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in range(col_count)) + " |",
    ]
    for row in padded[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _table_to_markdown(table: fitz.table.Table) -> str:
    try:
        md = table.to_markdown().strip()
        if md:
            return md
    except Exception:
        pass
    return _rows_to_markdown(table.extract())


def _extract_page_tables(page: fitz.Page) -> list[tuple[fitz.Rect, str]]:
    try:
        finder = page.find_tables()
    except Exception:
        return []

    tables: list[tuple[fitz.Rect, str]] = []
    for table in finder.tables:
        markdown = _table_to_markdown(table)
        if markdown:
            tables.append((table.bbox, markdown))
    return tables


def _block_overlaps_tables(block: tuple, table_bboxes: list[fitz.Rect]) -> bool:
    if len(block) < 4 or not table_bboxes:
        return False
    block_rect = fitz.Rect(block[0], block[1], block[2], block[3])
    block_area = block_rect.width * block_rect.height
    if block_area <= 0:
        return False
    for table_rect in table_bboxes:
        overlap = block_rect & table_rect
        if overlap.is_empty:
            continue
        overlap_area = overlap.width * overlap.height
        if overlap_area / block_area >= 0.35:
            return True
    return False


def _page_content_parts(page: fitz.Page) -> tuple[list[str], str | None]:
    """Legacy per-page extraction (find_tables + text blocks)."""
    table_items = _extract_page_tables(page)
    table_bboxes = [bbox for bbox, _ in table_items]
    page_parts: list[str] = [markdown for _, markdown in table_items]

    current_heading: str | None = None
    blocks = page.get_text("blocks")
    for block in blocks:
        if len(block) < 5:
            continue
        if _block_overlaps_tables(block, table_bboxes):
            continue
        text = str(block[4]).strip()
        if not text:
            continue
        heading = _detect_heading(text)
        if heading:
            current_heading = heading
        page_parts.append(text)

    return page_parts, current_heading


def _chunk_legacy(pdf_bytes: bytes) -> list[TextChunk]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[TextChunk] = []
    idx = 0
    current_heading: str | None = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_parts, page_heading = _page_content_parts(page)
        if page_heading:
            current_heading = page_heading

        if not page_parts:
            continue

        page_text = "\n\n".join(page_parts)
        for part in _split_page_text(page_text):
            chunks.append(
                TextChunk(
                    chunk_index=idx,
                    page=page_num + 1,
                    section_heading=current_heading,
                    pillar_hint=_infer_pillar(part, current_heading),
                    content=part,
                    token_estimate=_estimate_tokens(part),
                )
            )
            idx += 1

    doc.close()
    return chunks


def chunk_pdf_bytes(pdf_bytes: bytes) -> list[TextChunk]:
    try:
        chunks = _chunk_with_layout(pdf_bytes)
        logger.info("PDF chunked with pymupdf_layout (%d chunks)", len(chunks))
        return chunks
    except ImportError:
        logger.warning("pymupdf4llm not installed — falling back to legacy PDF chunker.")
    except Exception as exc:
        logger.warning("Layout chunker failed (%s) — falling back to legacy PDF chunker.", exc)

    chunks = _chunk_legacy(pdf_bytes)
    if not chunks:
        raise ValueError("PDF produced no text chunks — is it scanned/image-only?")
    logger.info("PDF chunked with legacy extractor (%d chunks)", len(chunks))
    return chunks


def chunk_pdf_file(path: Path | str) -> list[TextChunk]:
    return chunk_pdf_bytes(Path(path).read_bytes())
