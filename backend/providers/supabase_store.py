"""Backward-compatible alias for Report Parser document persistence."""

from agents.report_parser.store.document_store import DocumentStore, get_supabase

SupabaseStore = DocumentStore

__all__ = ["SupabaseStore", "DocumentStore", "get_supabase"]
