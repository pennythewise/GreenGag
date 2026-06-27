"""Extract pipeline: MiniLM pillar routing → per-pillar LLM → validate → persist."""

from __future__ import annotations

from typing import Any

from .llm.claim_extractor import ClaimExtractor
from .llm.claim_rules import validate_claim_for_pillar
from .llm.models import (
    ExtractionResponse,
    PillarRetrievalStatus,
    RetrievedChunk,
    llm_claim_to_extracted,
)
from .rag.pillar_queries import PILLARS
from .rag.retriever import RagRetriever
from ..store.document_store import DocumentStore
from config import settings
from models.schemas import (
    EsgPillar,
    ExtractedClaim,
    HighlightBox,
    PdfBlock,
    PdfDocument,
    ReportParserState,
)


class ExtractPipeline:
    def __init__(
        self,
        store: DocumentStore | None = None,
        retriever: RagRetriever | None = None,
        extractor: ClaimExtractor | None = None,
    ) -> None:
        self.store = store or DocumentStore()
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
            pillar_chunks, pillar_status = await self.retriever.retrieve(document_id)
            all_chunks = _dedupe_chunks(pillar_chunks)

            self.store.update_document(document_id, extract_status="extracting")
            extraction = ExtractionResponse()
            claims: list[ExtractedClaim] = []

            for pillar in PILLARS:
                chunks = pillar_chunks.get(pillar, [])
                status = pillar_status[pillar]

                if not chunks:
                    if status.status == "insufficient_text_retrieved":
                        extraction.extraction_notes.append(
                            f"{pillar}: insufficient text retrieved — no chunks available."
                        )
                    continue

                part = await self.extractor.extract_for_pillar(
                    filename=doc["original_filename"],
                    pillar=pillar,
                    chunks=chunks,
                    pillar_status={pillar: status.model_dump()},
                )

                if not extraction.document_title and part.document_title:
                    extraction.document_title = part.document_title
                if not extraction.reporting_entity and part.reporting_entity:
                    extraction.reporting_entity = part.reporting_entity
                if not extraction.reporting_year and part.reporting_year:
                    extraction.reporting_year = part.reporting_year
                extraction.extraction_notes.extend(part.extraction_notes)

                routing_scores = _aggregate_routing_scores(chunks)
                pillar_claim_count = 0

                for raw in part.claims:
                    if raw.confidence is not None and raw.confidence < 0.3:
                        extraction.extraction_notes.append(
                            f"Skipped low-confidence claim {raw.id} ({raw.confidence})."
                        )
                        continue

                    reject_reason = validate_claim_for_pillar(
                        raw,
                        expected_pillar=pillar,
                        routing_scores=routing_scores,
                        routing_confidence_floor=settings.pillar_routing_confidence_floor,
                    )
                    if reject_reason:
                        extraction.extraction_notes.append(
                            f"Rejected claim {raw.id}: {reject_reason}"
                        )
                        continue

                    if raw.pillar == pillar:
                        raw.id = _scoped_claim_id(pillar, raw.id)
                        claims.append(llm_claim_to_extracted(raw))
                        pillar_claim_count += 1
                    else:
                        raw.id = _scoped_claim_id(raw.pillar, raw.id)
                        claims.append(llm_claim_to_extracted(raw))
                        pillar_claim_count += 1
                        extraction.extraction_notes.append(
                            f"Kept claim {raw.id} under pillar '{raw.pillar}' "
                            f"(extract context '{pillar}', routing score "
                            f"{routing_scores.get(raw.pillar, 0.0):.2f} > "
                            f"{settings.pillar_routing_confidence_floor})."
                        )

                status.claims_extracted = pillar_claim_count
                if pillar_claim_count == 0 and status.chunks_selected > 0:
                    extraction.extraction_notes.append(
                        f"{pillar}: {status.chunks_selected} chunk(s) retrieved "
                        f"(best MiniLM score {status.best_score:.2f}) but no measurable "
                        f"claims passed validation — not inferred as absent from report."
                    )

            run_row = self.store.insert_extraction_run(
                {
                    "document_id": document_id,
                    "pillar_status": {k: v.model_dump() for k, v in pillar_status.items()},
                    "chunks_used": [c.model_dump() for c in all_chunks],
                    "extraction_notes": extraction.extraction_notes,
                    "model": settings.llm_extraction_model,
                    "embedding_model": settings.rag_pillar_routing_model,
                    "embedding_dims": 384,
                }
            )

            self.store.delete_claims(document_id)
            claim_rows = [_claim_row(document_id, run_row["id"], claim) for claim in claims]
            self.store.insert_claims(claim_rows)

            parser_state = _build_parser_state(extraction, claims, all_chunks, pillar_status)

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
                "chunks_used": len(all_chunks),
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


def _dedupe_chunks(
    pillar_chunks: dict[EsgPillar, list[RetrievedChunk]],
) -> list[RetrievedChunk]:
    seen: set[str] = set()
    out: list[RetrievedChunk] = []
    for pillar in PILLARS:
        for chunk in pillar_chunks.get(pillar, []):
            if chunk.id not in seen:
                seen.add(chunk.id)
                out.append(chunk)
    return out


def _aggregate_routing_scores(
    chunks: list[RetrievedChunk],
) -> dict[EsgPillar, float]:
    scores: dict[EsgPillar, float] = {p: 0.0 for p in PILLARS}
    for chunk in chunks:
        for pillar, score in chunk.pillar_scores.items():
            scores[pillar] = max(scores[pillar], score)
    return scores


def _scoped_claim_id(pillar: EsgPillar, claim_id: str) -> str:
    prefix = f"{pillar}-"
    if claim_id.startswith(prefix):
        return claim_id
    return f"{prefix}{claim_id}"


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
    pillar_status: dict[EsgPillar, PillarRetrievalStatus],
) -> ReportParserState:
    document = _build_pdf_document(extraction, claims, chunks)
    per_pillar = ", ".join(
        f"{p}={pillar_status[p].claims_extracted}" for p in PILLARS
    )
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool=(
            f"minilm_routing::{settings.rag_pillar_routing_model} + "
            f"openai::{settings.llm_extraction_model}"
        ),
        rationale_trail=[
            (
                f"MiniLM routed top {settings.rag_chunks_per_pillar} chunks per pillar "
                f"({len(chunks)} unique chunks)."
            ),
            f"Per-pillar OpenAI extraction: {per_pillar} claims.",
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
