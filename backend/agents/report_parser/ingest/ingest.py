"""Ingest pipeline: PDF upload → chunk → embed → Supabase."""

from __future__ import annotations

import uuid
from typing import Any

from .chunker import TextChunk, chunk_pdf_bytes
from .hashing import pdf_content_hash
from ..store.document_store import DocumentStore
from config import settings
from providers.embeddings import OpenAIEmbedder


class IngestPipeline:
    def __init__(
        self,
        store: DocumentStore | None = None,
        embedder: OpenAIEmbedder | None = None,
    ) -> None:
        self.store = store or DocumentStore()
        self.embedder = embedder or OpenAIEmbedder()

    async def run(self, *, filename: str, pdf_bytes: bytes) -> dict[str, Any]:
        content_hash = pdf_content_hash(pdf_bytes)
        existing = self.store.find_ready_by_hash(
            content_hash,
            settings.embedding_model,
            settings.embedding_dimensions,
        )
        if existing:
            return {**existing, "deduplicated": True}

        doc_id = str(uuid.uuid4())
        storage_path = f"{doc_id}/{filename}"

        doc = self.store.create_document(
            storage_path=storage_path,
            original_filename=filename,
            content_hash=content_hash,
            embedding_model=settings.embedding_model,
            embedding_dims=settings.embedding_dimensions,
        )
        document_id = doc["id"]

        try:
            self.store.update_document(document_id, ingest_status="uploading")
            self.store.upload_pdf(storage_path, pdf_bytes)

            self.store.update_document(document_id, ingest_status="chunking")
            chunks = chunk_pdf_bytes(pdf_bytes)
            if not chunks:
                raise ValueError("PDF produced no text chunks — is it scanned/image-only?")

            self.store.update_document(document_id, ingest_status="embedding")
            embeddings = await self.embedder.embed_texts([c.content for c in chunks])
            if len(embeddings) != len(chunks):
                raise RuntimeError("Embedding count mismatch.")

            self.store.delete_chunks(document_id)
            rows = [_chunk_row(document_id, chunk, emb) for chunk, emb in zip(chunks, embeddings)]
            self.store.insert_chunks(rows)

            result = self.store.update_document(
                document_id,
                ingest_status="ready",
                extract_status="pending",
                chunk_count=len(chunks),
                error_message=None,
            )
            return {**result, "deduplicated": False}
        except Exception as exc:
            self.store.update_document(
                document_id,
                ingest_status="failed",
                error_message=str(exc),
            )
            raise


def _chunk_row(document_id: str, chunk: TextChunk, embedding: list[float]) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "chunk_index": chunk.chunk_index,
        "page": chunk.page,
        "section_heading": chunk.section_heading,
        "pillar_hint": chunk.pillar_hint,
        "content": chunk.content,
        "token_estimate": chunk.token_estimate,
        "embedding": embedding,
    }
