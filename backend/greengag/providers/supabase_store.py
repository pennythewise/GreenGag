"""Supabase client wrapper for documents, chunks, claims."""

from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from greengag.config import settings


def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
    return create_client(settings.supabase_url, settings.supabase_service_key)


class SupabaseStore:
    BUCKET = "documents"

    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_supabase()

    def create_document(
        self,
        *,
        storage_path: str,
        original_filename: str,
        embedding_model: str,
        embedding_dims: int,
    ) -> dict[str, Any]:
        row = {
            "storage_path": storage_path,
            "original_filename": original_filename,
            "ingest_status": "pending",
            "embedding_model": embedding_model,
            "embedding_dims": embedding_dims,
        }
        resp = self.client.table("documents").insert(row).execute()
        return resp.data[0]

    def update_document(self, document_id: str, **fields: Any) -> dict[str, Any]:
        resp = (
            self.client.table("documents")
            .update(fields)
            .eq("id", document_id)
            .execute()
        )
        return resp.data[0]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("documents")
            .select("*")
            .eq("id", document_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def upload_pdf(self, storage_path: str, pdf_bytes: bytes) -> None:
        self.client.storage.from_(self.BUCKET).upload(
            storage_path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )

    def download_pdf(self, storage_path: str) -> bytes:
        return self.client.storage.from_(self.BUCKET).download(storage_path)

    def insert_chunks(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        # Batch inserts to avoid payload limits.
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            self.client.table("document_chunks").insert(rows[i : i + batch_size]).execute()

    def delete_chunks(self, document_id: str) -> None:
        self.client.table("document_chunks").delete().eq("document_id", document_id).execute()

    def match_chunks(
        self,
        document_id: str,
        query_embedding: list[float],
        pillar: str,
        match_count: int,
    ) -> list[dict[str, Any]]:
        resp = self.client.rpc(
            "match_document_chunks",
            {
                "p_document_id": document_id,
                "p_query_embedding": query_embedding,
                "p_pillar": pillar,
                "p_match_count": match_count,
            },
        ).execute()
        return resp.data or []

    def list_chunks(self, document_id: str) -> list[dict[str, Any]]:
        resp = (
            self.client.table("document_chunks")
            .select("id, chunk_index, page, section_heading, content")
            .eq("document_id", document_id)
            .order("chunk_index")
            .execute()
        )
        return resp.data or []

    def insert_extraction_run(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("extraction_runs").insert(row).execute()
        return resp.data[0]

    def delete_claims(self, document_id: str) -> None:
        self.client.table("claims").delete().eq("document_id", document_id).execute()

    def insert_claims(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self.client.table("claims").insert(rows).execute()

    def list_claims(self, document_id: str) -> list[dict[str, Any]]:
        resp = (
            self.client.table("claims")
            .select("*")
            .eq("document_id", document_id)
            .execute()
        )
        return resp.data or []
