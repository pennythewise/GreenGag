"""Page-aware PDF chunking with pillar hints."""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from greengag.models.extraction import TextChunk

# Rough token estimate: ~4 chars per token for English prose.
CHARS_PER_TOKEN = 4
TARGET_TOKENS = 800
OVERLAP_TOKENS = 128
TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN

HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\s+)?[A-Z][A-Za-z0-9\s,&\-–—]{2,60}$")

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
        # Hard-split long paragraphs with overlap.
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

    # Apply overlap between adjacent chunks.
    overlapped: list[str] = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            overlapped.append(chunk)
            continue
        prev_tail = chunks[i - 1][-OVERLAP_CHARS:]
        overlapped.append(f"{prev_tail}\n{chunk}".strip())
    return overlapped


def _detect_heading(block_text: str) -> str | None:
    first_line = block_text.strip().split("\n", 1)[0].strip()
    if HEADING_RE.match(first_line) and len(first_line) < 80:
        return first_line
    return None


def chunk_pdf_bytes(pdf_bytes: bytes) -> list[TextChunk]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[TextChunk] = []
    idx = 0
    current_heading: str | None = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        page_parts: list[str] = []
        for block in blocks:
            if len(block) < 5:
                continue
            text = str(block[4]).strip()
            if not text:
                continue
            heading = _detect_heading(text)
            if heading:
                current_heading = heading
            page_parts.append(text)

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


def chunk_pdf_file(path: Path | str) -> list[TextChunk]:
    return chunk_pdf_bytes(Path(path).read_bytes())
