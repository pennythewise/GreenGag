"""Extract pipeline: RAG retrieve → OpenAI extract → validate → persist."""

from __future__ import annotations

from typing import Any

from greengag.config import settings
from greengag.models.extraction import (
    ExtractionResponse,
    RetrievedChunk,
    llm_claim_to_extracted,
)
from greengag.models.schemas import (
    ExtractedClaim,
    HighlightBox,
    PdfBlock,
    PdfDocument,
    PdfPage,
    ReportParserState,
)
from greengag.providers.supabase_store import SupabaseStore
from greengag.services.extract.claim_extractor import ClaimExtractor
from greengag.services.rag.retriever import RagRetriever


class ExtractPipeline:
    def __init__(
        self,
        store: SupabaseStore | None = None,
        retriever: RagRetriever | None = None,
        extractor: ClaimExtractor | None = None,
    ) -> None:
        self.store = store or SupabaseStore()
        self.retriever = retriever or RagRetriever(store=self.store)
        self.extractor = extractor or ClaimExtractor()

    async def run(self, document_id: str) -> dict[str, Any]:
        doc = self.store.get_document(document_id)
        if not doc:
            raise LookupError(f"Document {document_id} not found.")
        if doc.get("ingest_status") != "ready":
            raise ValueError(
                f"Document ingest_status is '{doc.get('ingest_status')}', expected 'ready'."
            )

        try:
            self.store.update_document(document_id, extract_status="retrieving")
            chunks, pillar_status = await self.retriever.retrieve(document_id)

            self.store.update_document(document_id, extract_status="extracting")
            extraction = await self.extractor.extract(
                filename=doc["original_filename"],
                chunks=chunks,
                pillar_status={
                    k: v.model_dump() for k, v in pillar_status.items()
                },
            )

            claims: list[ExtractedClaim] = []
            for raw in extraction.claims:
                if raw.confidence is not None and raw.confidence < 0.3:
                    extraction.extraction_notes.append(
                        f"Skipped low-confidence claim {raw.id} ({raw.confidence})."
                    )
                    continue
                claims.append(llm_claim_to_extracted(raw))

            run_row = self.store.insert_extraction_run(
                {
                    "document_id": document_id,
                    "pillar_status": {k: v.model_dump() for k, v in pillar_status.items()},
                    "chunks_used": [c.model_dump() for c in chunks],
                    "extraction_notes": extraction.extraction_notes,
                    "model": settings.llm_extraction_model,
                    "embedding_model": settings.embedding_model,
                    "embedding_dims": settings.embedding_dimensions,
                }
            )

            self.store.delete_claims(document_id)
            claim_rows = [
                _claim_row(document_id, run_row["id"], claim) for claim in claims
            ]
            self.store.insert_claims(claim_rows)

            parser_state = _build_parser_state(extraction, claims, chunks)

            updated = self.store.update_document(
                document_id,
                extract_status="complete",
                claim_count=len(claims),
                document_title=extraction.document_title or doc.get("document_title"),
                reporting_entity=extraction.reporting_entity or doc.get("reporting_entity"),
                reporting_year=extraction.reporting_year or doc.get("reporting_year"),
                error_message=None,
            )

            return {
                "document": updated,
                "extraction_run_id": run_row["id"],
                "pillar_status": {k: v.model_dump() for k, v in pillar_status.items()},
                "chunks_used": len(chunks),
                "claims": [c.model_dump() for c in claims],
                "report_parser": parser_state.model_dump(),
                "extraction_notes": extraction.extraction_notes,
            }
        except Exception as exc:
            self.store.update_document(
                document_id,
                extract_status="failed",
                error_message=str(exc),
            )
            raise
def _claim_row(document_id: str, run_id: str, claim: ExtractedClaim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "document_id": document_id,
        "extraction_run_id": run_id,
        "pillar": claim.pillar,
        "category": claim.category or "Uncategorized",
        "claim_type": claim.claim_type or "other",
        "label": claim.label,
        "raw_text": claim.raw_text,
        "entity": claim.entity,
        "metric": claim.metric,
        "target_value": claim.target_value,
        "achieved_value": claim.achieved_value,
        "baseline_value": claim.baseline_value,
        "time_period": claim.time_period,
        "location": claim.location,
        "unit": claim.unit,
        "page": claim.page,
        "section_heading": claim.section_heading,
        "key_metrics": claim.key_metrics,
        "confidence": claim.confidence,
        "claimed_reduction_pct": claim.claimed_reduction_pct,
        "material_class": claim.material_class,
        "stated_spend_usd": claim.stated_spend_usd,
        "highlight": claim.highlight.model_dump() if claim.highlight else None,
    }


def _build_parser_state(
    extraction: ExtractionResponse,
    claims: list[ExtractedClaim],
    chunks: list[RetrievedChunk],
) -> ReportParserState:
    document = _build_pdf_document(extraction, claims, chunks)
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool=f"rag_extractor::{settings.llm_extraction_model}",
        rationale_trail=[
            f"Retrieved {len(chunks)} RAG chunks across E/S/G pillars.",
            f"OpenAI ({settings.llm_extraction_model}) normalized {len(claims)} claims.",
            *(
                [f"Note: {n}" for n in extraction.extraction_notes[:3]]
                if extraction.extraction_notes
                else []
            ),
        ],
        document=document,
        extracted_claims=claims,
    )


def _build_pdf_document(
    extraction: ExtractionResponse,
    claims: list[ExtractedClaim],
    chunks: list[RetrievedChunk],
) -> PdfDocument:
    title = extraction.document_title or "ESG Report"
    pages_map: dict[int, PdfPage] = {}

    for chunk in chunks:
        page_no = chunk.page or 1
        if page_no not in pages_map:
            pages_map[page_no] = PdfPage(
                page=page_no,
                heading=chunk.section_heading or f"Page {page_no}",
                blocks=[],
            )
        pages_map[page_no].blocks.append(
            PdfBlock(id=f"chunk-{chunk.id[:8]}", text=chunk.content[:600])
        )

    for claim in claims:
        page_no = claim.page or 1
        if page_no not in pages_map:
            pages_map[page_no] = PdfPage(
                page=page_no,
                heading=claim.section_heading or f"Page {page_no}",
                blocks=[],
            )
        highlight = claim.highlight or HighlightBox(page=page_no, x=8, y=30, w=84, h=9)
        claim.highlight = highlight
        pages_map[page_no].blocks.append(
            PdfBlock(id=f"claim-{claim.id}", text=claim.raw_text, claim_id=claim.id)
        )

    return PdfDocument(
        title=title,
        pages=sorted(pages_map.values(), key=lambda p: p.page),
    )
