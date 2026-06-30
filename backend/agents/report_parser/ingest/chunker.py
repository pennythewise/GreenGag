"""Page-aware PDF chunking via pymupdf4llm layout (ingest pipeline)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz
from pydantic import BaseModel

logger = logging.getLogger("greengag.report_parser.ingest.chunker")

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
        "carbon", "emission", "energy", "renewable", "water", "waste",
        "biodiversity", "climate", "ghg", "net zero", "recycl", "environment",
    ),
    "social": (
        "employee", "worker", "safety", "community", "diversity", "human rights",
        "training", "health", "labour", "labor", "social", "stakeholder",
    ),
    "governance": (
        "board", "governance", "ethics", "compliance", "audit", "risk",
        "anti-corruption", "transparency", "policy", "whistle",
    ),
}


class TextChunk(BaseModel):
    chunk_index: int
    page: int
    section_heading: str | None
    pillar_hint: str | None
    content: str
    token_estimate: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _infer_pillar(text: str, heading: str | None) -> str | None:
    hay = f"{heading or ''} {text}".lower()
    scores = {pillar: sum(1 for kw in kws if kw in hay) for pillar, kws in PILLAR_KEYWORDS.items()}
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
    text: str, toc_items: list, page_num: int, fallback: str | None
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
    return "\n".join(rows) if len(rows) >= 2 else None


def _sanitize_layout_markdown(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    def _replace_picture_block(match: re.Match[str]) -> str:
        recovered = _extract_table_rows_from_picture_block(match.group(0))
        return f"\n\n{recovered}\n\n" if recovered else ""

    text = PICTURE_TEXT_BLOCK_RE.sub(_replace_picture_block, text)
    text = PICTURE_OMITTED_RE.sub("", text)
    text = re.sub(r"^(#{1,6})\s+\*\*(.+?)\*\*\s*$", r"\1 \2", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if BROKEN_TABLE_LINE_RE.match(stripped.strip()):
            continue
        if re.fullmatch(r"[-|_\s]+", stripped.strip()):
            continue
        lines.append(stripped)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _detect_heading(block_text: str) -> str | None:
    first_line = block_text.strip().split("\n", 1)[0].strip()
    if HEADING_RE.match(first_line) and len(first_line) < 80:
        return first_line
    return None


def _chunk_with_layout(pdf_bytes: bytes) -> list[TextChunk]:
    import pymupdf4llm  # noqa: F401

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
            text = _sanitize_layout_markdown(raw_text)
            if not text:
                continue

            page_heading = _heading_from_layout_page(
                text,
                page_chunk.get("toc_items") or [],
                page_num,
                current_heading,
            )
            if page_heading:
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


def _chunk_legacy_blocks(pdf_bytes: bytes) -> list[TextChunk]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[TextChunk] = []
    idx = 0
    current_heading: str | None = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_parts: list[str] = []
        for block in page.get_text("blocks"):
            if len(block) < 5:
                continue
            text = str(block[4]).strip()
            if not text:
                continue
            heading = _detect_heading(text)
            if heading:
                current_heading = heading
            page_parts.append(text)

        if not page_parts:
            continue
        for part in _split_page_text("\n\n".join(page_parts)):
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
        logger.warning("pymupdf4llm not installed — falling back to block chunker.")
    except Exception as exc:
        logger.warning("Layout chunker failed (%s) — falling back to block chunker.", exc)

    chunks = _chunk_legacy_blocks(pdf_bytes)
    if not chunks:
        raise ValueError("PDF produced no text chunks — is it scanned/image-only?")
    logger.info("PDF chunked with legacy blocks (%d chunks)", len(chunks))
    return chunks


def chunk_pdf_file(path: Path | str) -> list[TextChunk]:
    return chunk_pdf_bytes(Path(path).read_bytes())
