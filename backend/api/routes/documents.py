"""Document ingest / extract API (two-phase Report Parser pipeline)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from mocks import fixtures
from models.schemas import ExtractedClaim, HighlightBox, ReportParserState
from agents.report_parser import ExtractPipeline, IngestPipeline
from agents.report_parser.report.renderer import render_extraction_report_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


class IngestResponse(BaseModel):
    document_id: str
    original_filename: str
    ingest_status: str
    chunk_count: int
    deduplicated: bool = False
    mode: str


class ExtractResponse(BaseModel):
    document_id: str
    extract_status: str
    claim_count: int
    claims: list[ExtractedClaim]
    report_parser: ReportParserState
    pillar_status: dict[str, Any] = Field(default_factory=dict)
    extraction_notes: list[str] = Field(default_factory=list)
    mode: str


class DocumentStatusResponse(BaseModel):
    document: dict[str, Any]
    claims: list[ExtractedClaim] = Field(default_factory=list)


def _mock_ingest(filename: str) -> IngestResponse:
    return IngestResponse(
        document_id="mock-document",
        original_filename=filename,
        ingest_status="ready",
        chunk_count=24,
        mode="mock",
    )


def _mock_extract() -> ExtractResponse:
    parser = fixtures.report_parser_state()
    return ExtractResponse(
        document_id="mock-document",
        extract_status="complete",
        claim_count=len(parser.extracted_claims),
        claims=parser.extracted_claims,
        report_parser=parser,
        pillar_status={
            "environment": {"status": "ok", "best_score": 0.82, "chunks_selected": 8},
            "social": {"status": "ok", "best_score": 0.71, "chunks_selected": 6},
            "governance": {"status": "ok", "best_score": 0.68, "chunks_selected": 5},
        },
        extraction_notes=["Mock extraction — pipeline keys not configured or mock mode."],
        mode="mock",
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    if not settings.pipeline_ready():
        return _mock_ingest(file.filename)

    try:
        result = await IngestPipeline().run(filename=file.filename, pdf_bytes=pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return IngestResponse(
        document_id=result["id"],
        original_filename=result["original_filename"],
        ingest_status=result["ingest_status"],
        chunk_count=result.get("chunk_count", 0),
        deduplicated=bool(result.get("deduplicated")),
        mode="live",
    )


@router.post("/{document_id}/extract", response_model=ExtractResponse)
async def extract_document(document_id: str) -> ExtractResponse:
    if not settings.pipeline_ready() or document_id == "mock-document":
        return _mock_extract()

    try:
        result = await ExtractPipeline().run(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    doc = result["document"]
    return ExtractResponse(
        document_id=doc["id"],
        extract_status=doc["extract_status"],
        claim_count=doc.get("claim_count", 0),
        claims=[ExtractedClaim.model_validate(c) for c in result["claims"]],
        report_parser=ReportParserState.model_validate(result["report_parser"]),
        pillar_status=result.get("pillar_status", {}),
        extraction_notes=result.get("extraction_notes", []),
        mode="live",
    )


@router.post("/{document_id}/report/pdf")
async def download_extraction_report(document_id: str) -> StreamingResponse:
    """Generate a PDF extraction report (cover, summary, insights, claim cards)."""
    try:
        pdf_bytes, filename = render_extraction_report_pdf(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="WeasyPrint is not installed — see backend/README.md for setup.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document(document_id: str) -> DocumentStatusResponse:
    if document_id == "mock-document" or not settings.pipeline_ready():
        mock = _mock_extract()
        return DocumentStatusResponse(
            document={
                "id": mock.document_id,
                "original_filename": "2025_Sustainability_Net-Zero_Pathway.pdf",
                "ingest_status": "ready",
                "extract_status": mock.extract_status,
                "claim_count": mock.claim_count,
            },
            claims=mock.claims,
        )

    from agents.report_parser.store.document_store import DocumentStore

    store = DocumentStore()
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    rows = store.list_claims(document_id)
    claims = [_row_to_claim(r) for r in rows]
    return DocumentStatusResponse(document=doc, claims=claims)


def _row_to_claim(row: dict[str, Any]) -> ExtractedClaim:
    raw_highlight = row.get("highlight")
    highlight = HighlightBox.model_validate(raw_highlight) if raw_highlight else None
    return ExtractedClaim(
        id=row["id"],
        label=row["label"],
        raw_text=row["raw_text"],
        pillar=row.get("pillar"),
        category=row.get("category"),
        claim_type=row.get("claim_type"),
        entity=row.get("entity"),
        metric=row.get("metric"),
        target_value=row.get("target_value"),
        achieved_value=row.get("achieved_value"),
        baseline_value=row.get("baseline_value"),
        time_period=row.get("time_period"),
        location=row.get("location"),
        unit=row.get("unit"),
        page=row.get("page"),
        section_heading=row.get("section_heading"),
        key_metrics=row.get("key_metrics") or {},
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        claimed_reduction_pct=(
            float(row["claimed_reduction_pct"])
            if row.get("claimed_reduction_pct") is not None
            else None
        ),
        material_class=row.get("material_class"),
        stated_spend_usd=(
            float(row["stated_spend_usd"]) if row.get("stated_spend_usd") is not None else None
        ),
        highlight=highlight,
    )
