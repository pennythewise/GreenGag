"""Build Jinja context and render extraction report PDF."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mocks import fixtures
from models.schemas import ExtractedClaim
from ..store.document_store import DocumentStore

from .insights import (
    DISCLAIMER,
    build_conclusion,
    build_insights,
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PILLARS = ("environment", "social", "governance")


def _claim_to_view(claim: ExtractedClaim | dict[str, Any]) -> dict[str, Any]:
    if isinstance(claim, ExtractedClaim):
        data = claim.model_dump()
    else:
        data = dict(claim)

    fields: list[dict[str, str]] = []
    if data.get("pillar"):
        fields.append({"key": "pillar", "value": str(data["pillar"])})
    if data.get("claim_type"):
        fields.append({"key": "claim_type", "value": str(data["claim_type"])})
    if data.get("category"):
        fields.append({"key": "category", "value": str(data["category"])})
    if data.get("entity"):
        fields.append({"key": "entity", "value": str(data["entity"])})
    if data.get("metric"):
        fields.append({"key": "metric", "value": str(data["metric"])})
    if data.get("target_value"):
        fields.append({"key": "target_value", "value": str(data["target_value"])})
    if data.get("achieved_value"):
        fields.append({"key": "achieved_value", "value": str(data["achieved_value"])})
    if data.get("baseline_value"):
        fields.append({"key": "baseline_value", "value": str(data["baseline_value"])})
    if data.get("time_period"):
        fields.append({"key": "time_period", "value": str(data["time_period"])})
    if data.get("unit"):
        fields.append({"key": "unit", "value": str(data["unit"])})
    if data.get("page") is not None:
        fields.append({"key": "page", "value": f"p.{data['page']}"})
    if data.get("section_heading"):
        fields.append({"key": "section", "value": str(data["section_heading"])})
    conf = data.get("confidence")
    if conf is not None:
        fields.append({"key": "confidence", "value": f"{round(float(conf) * 100)}%"})

    return {
        "id": data.get("id", ""),
        "label": data.get("label", ""),
        "raw_text": data.get("raw_text", ""),
        "pillar": data.get("pillar"),
        "fields": fields,
    }


def _summary_stats(claims: list[dict[str, Any]]) -> dict[str, Any]:
    by_pillar = {p: 0 for p in PILLARS}
    pages: set[int] = set()
    confidences: list[float] = []

    for claim in claims:
        pillar = claim.get("pillar")
        if pillar in by_pillar:
            by_pillar[pillar] += 1
        page = claim.get("page")
        if isinstance(page, int):
            pages.add(page)
        if claim.get("confidence") is not None:
            confidences.append(float(claim["confidence"]))

    return {
        "total_claims": len(claims),
        "by_pillar": by_pillar,
        "pages_covered": sorted(pages),
        "avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
    }


def _mock_context() -> dict[str, Any]:
    parser = fixtures.report_parser_state()
    claims = [c.model_dump() for c in parser.extracted_claims]
    notes = ["Mock extraction — demonstration data only."]
    return _assemble_context(
        document={
            "id": "mock-document",
            "original_filename": "2025_Sustainability_Net-Zero_Pathway.pdf",
            "document_title": parser.document.title if parser.document else None,
            "reporting_entity": "Malaya BuildCorp Group",
            "reporting_year": "2025",
        },
        claims=claims,
        extraction_notes=notes,
        pillar_status={
            "environment": {"status": "ok", "best_score": 0.82},
            "social": {"status": "ok", "best_score": 0.71},
            "governance": {"status": "ok", "best_score": 0.68},
        },
    )


def _assemble_context(
    *,
    document: dict[str, Any],
    claims: list[dict[str, Any]],
    extraction_notes: list[str],
    pillar_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary_stats(claims)
    return {
        "report_title": "GreenGag ESG Extraction Report",
        "generated_at": datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC"),
        "document": document,
        "summary": summary,
        "insights": build_insights(claims, extraction_notes, pillar_status),
        "claims": [_claim_to_view(c) for c in claims],
        "conclusion": build_conclusion(summary["total_claims"]),
        "disclaimer": DISCLAIMER,
    }


def load_report_context(document_id: str) -> dict[str, Any]:
    if document_id == "mock-document":
        return _mock_context()

    store = DocumentStore()
    doc = store.get_document(document_id)
    if not doc:
        raise LookupError(f"Document {document_id} not found.")
    if doc.get("extract_status") != "complete":
        raise ValueError(
            "Document extraction is not complete — run extract before generating a report."
        )

    rows = store.list_claims(document_id)
    run = store.get_latest_extraction_run(document_id)
    notes = list(run.get("extraction_notes") or []) if run else []
    pillar_status = run.get("pillar_status") if run else {}

    return _assemble_context(
        document=doc,
        claims=rows,
        extraction_notes=notes,
        pillar_status=pillar_status if isinstance(pillar_status, dict) else {},
    )


def render_extraction_report_pdf(document_id: str) -> tuple[bytes, str]:
    context = load_report_context(document_id)
    html = _render_html(context)
    pdf_bytes = _html_to_pdf(html)
    filename = context["document"].get("original_filename", "report")
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    download_name = f"GreenGag-extraction-{safe.rsplit('.', 1)[0]}.pdf"
    return pdf_bytes, download_name


def _render_html(context: dict[str, Any]) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template("extraction_report.html").render(**context)


def _html_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import CSS, HTML
    except (ImportError, OSError) as exc:
        raise ImportError(
            "WeasyPrint native libraries are not available — see backend/README.md."
        ) from exc

    css_path = TEMPLATE_DIR / "greengag_report.css"
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(
        stylesheets=[CSS(filename=str(css_path))]
    )
