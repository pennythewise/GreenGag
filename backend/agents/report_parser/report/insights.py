"""Rule-based insight bullets for extraction reports."""

from __future__ import annotations

from typing import Any

PILLARS = ("environment", "social", "governance")
LOW_CONFIDENCE = 0.7


def build_insights(
    claims: list[dict[str, Any]],
    extraction_notes: list[str],
    pillar_status: dict[str, Any] | None = None,
) -> list[str]:
    insights: list[str] = []
    by_pillar = {p: 0 for p in PILLARS}
    pages: set[int] = set()
    low_conf: list[str] = []

    for claim in claims:
        pillar = claim.get("pillar")
        if pillar in by_pillar:
            by_pillar[pillar] += 1
        page = claim.get("page")
        if isinstance(page, int):
            pages.add(page)
        conf = claim.get("confidence")
        if conf is not None and float(conf) < LOW_CONFIDENCE:
            low_conf.append(claim.get("label") or claim.get("id", "claim"))

    for pillar, count in by_pillar.items():
        if count == 0:
            status = (pillar_status or {}).get(pillar, {})
            chunks_selected = (
                status.get("chunks_selected", 0) if isinstance(status, dict) else 0
            )
            if chunks_selected > 0:
                best = status.get("best_score")
                score_txt = f"{float(best):.2f}" if best is not None else "n/a"
                insights.append(
                    f"No measurable {pillar} claims passed validation after retrieving "
                    f"{chunks_selected} chunk(s) (best MiniLM score {score_txt}) — "
                    f"this does not mean the report omits {pillar} content."
                )
            elif isinstance(status, dict) and status.get("status") == "insufficient_text_retrieved":
                insights.append(
                    f"Insufficient {pillar} text retrieved from the document — "
                    f"extraction could not run for this pillar."
                )

    if pages:
        sorted_pages = sorted(pages)
        insights.append(
            f"Claims span {len(sorted_pages)} page(s): "
            f"p.{sorted_pages[0]}–p.{sorted_pages[-1]}."
            if len(sorted_pages) > 1
            else f"All extracted claims reference page {sorted_pages[0]}."
        )

    if low_conf:
        sample = ", ".join(low_conf[:3])
        extra = f" (+{len(low_conf) - 3} more)" if len(low_conf) > 3 else ""
        insights.append(
            f"{len(low_conf)} claim(s) below {int(LOW_CONFIDENCE * 100)}% confidence: "
            f"{sample}{extra}."
        )

    if pillar_status:
        for pillar, status in pillar_status.items():
            if isinstance(status, dict) and status.get("status") == "insufficient_text_retrieved":
                insights.append(
                    f"RAG retrieval for {pillar} returned insufficient text (best score "
                    f"{status.get('best_score', 'n/a')}) — claims in this pillar may be incomplete."
                )

    for note in extraction_notes[:5]:
        note = str(note).strip()
        if note and note not in insights:
            insights.append(note)

    if not insights:
        insights.append(
            "Extraction completed without notable coverage gaps in the rule-based checks."
        )

    return insights


def build_conclusion(claim_count: int) -> str:
    if claim_count == 0:
        return (
            "No measurable ESG claims were extracted from this document. "
            "A human reviewer should inspect the source PDF before relying on this output."
        )
    return (
        f"{claim_count} explicit ESG claim(s) were structured for human review. "
        "This report documents what the company stated — not whether those statements are accurate, "
        "complete, or free from greenwashing."
    )


DISCLAIMER = (
    "GreenGag provides decision-support risk indicators, not legal determinations. "
    "Extracted claims require independent verification against financial, media, and geospatial evidence "
    "before any compliance or investment action."
)
