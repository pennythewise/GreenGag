"""SHA-256 content hash for PDF deduplication."""

from __future__ import annotations

import hashlib


def pdf_content_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()
