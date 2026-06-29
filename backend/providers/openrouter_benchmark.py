"""Live industry benchmarking via OpenRouter only (google/gemini-2.5-flash:online).

Uses the OpenRouter API exclusively — never calls Google AI / Gemini direct endpoints.
GHG claims use a standardised intensity metric:
    tCO₂e / RM million revenue

For every peer in the registry, OpenRouter searches for the company's
latest published Scope 1+2 GHG total (tCO₂e), divides by the locally-stored
FY2025 revenue, and compares that intensity band against the target claim.
Non-GHG claims (safety, water, waste …) use a general peer comparison.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from config import settings
from models.schemas import ExtractedClaim
from providers.construction_peer_registry import (
    CompanyProfile,
    ConstructionBenchmarkContext,
    resolve_benchmark_context,
)

logger = logging.getLogger("greengag.openrouter_benchmark")

ALLOWED_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
URL_RE = re.compile(r"https?://[^\s\])\"']+")

# Keywords that mark a claim as GHG / carbon-related
_GHG_KEYWORDS = re.compile(
    r"\b(ghg|greenhouse|co2|co₂|carbon|scope\s*[123]|emission|tco2|tco₂|decarboni[sz]|net.?zero|climate)\b",
    re.IGNORECASE,
)

BENCHMARK_UNIT = "tCO₂e / RM million revenue"
OPENROUTER_BENCHMARK_MODEL = "google/gemini-2.5-flash"


@dataclass(frozen=True)
class PeerIntensityRecord:
    company_name: str
    revenue_rm_million: float | None
    scope_1_2_tco2e: float | None
    scope_3_tco2e: float | None
    total_scope_123_tco2e: float | None
    intensity_scope_12: float | None
    intensity_scope_3: float | None
    intensity_total: float | None
    data_year: str | None
    data_found: bool
    source: str
    is_target: bool = False

    @property
    def intensity(self) -> float | None:
        """Backward-compatible alias for scope 1+2 intensity."""
        return self.intensity_scope_12


@dataclass(frozen=True)
class BenchmarkEvidence:
    score: float
    contradiction: bool
    evidence_snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    rationale: str = ""
    used_live_search: bool = False
    provider: str = "none"
    peer_context: ConstructionBenchmarkContext | None = None
    peer_intensity_table: list[PeerIntensityRecord] = field(default_factory=list)
    benchmark_unit: str = BENCHMARK_UNIT
    is_ghg_claim: bool = False
    insights: str = ""
    conclusion: str = ""
    tldr: str = ""
    peer_intensity_range: str = ""


async def benchmark_claim_live(
    claim: ExtractedClaim,
    *,
    reporting_entity: str | None = None,
) -> BenchmarkEvidence | None:
    if not settings.live_benchmark_ready():
        return None

    context = resolve_benchmark_context(
        reporting_entity=reporting_entity,
        claim_entity=claim.entity,
    )

    return await asyncio.to_thread(_benchmark_claim_sync, claim, context)


def _unresolved_profile_evidence(context: ConstructionBenchmarkContext) -> BenchmarkEvidence:
    return BenchmarkEvidence(
        score=0.25,
        contradiction=False,
        evidence_snippets=[
            f"No local construction peer profile found for '{context.canonical_name}'."
        ],
        sources=["GreenGag construction peer registry"],
        rationale=(
            f"Benchmark skipped live web search: '{context.canonical_name}' is not in the "
            "Malaysian construction peer registry. Add the company to "
            "backend/data/construction_company_profiles.json to enable peer comparison."
        ),
        used_live_search=False,
        provider="registry:unresolved",
        peer_context=context,
    )


def _benchmark_claim_sync(
    claim: ExtractedClaim,
    context: ConstructionBenchmarkContext,
) -> BenchmarkEvidence | None:
    if not settings.openrouter_api_key:
        return None

    base_url = (settings.openrouter_base_url or "").lower()
    if "openrouter.ai" not in base_url:
        logger.error(
            "Industry benchmark requires OpenRouter (openrouter.ai); got base_url=%s",
            settings.openrouter_base_url,
        )
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    ghg = _is_ghg_claim(claim)
    model = settings.openrouter_online_model
    if OPENROUTER_BENCHMARK_MODEL not in model:
        logger.warning(
            "OPENROUTER_MODEL=%s; expected %s via OpenRouter (no direct Google Gemini).",
            model,
            OPENROUTER_BENCHMARK_MODEL,
        )
    prompt = _prompt_ghg_intensity(claim, context) if ghg else _prompt_general(claim, context)

    try:
        client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an ESG auditor benchmarking Malaysian construction companies. "
                        "Search sustainability and ESG reports (not financial statements alone) "
                        "for Scope 1+2, Scope 3, and total GHG data. Return ONLY valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        logger.warning("OpenRouter live benchmark failed: %s", exc)
        return None

    message = response.choices[0].message
    text = message.content or ""
    payload = _parse_json(text)
    if not payload:
        return None

    # Collect URL sources from body text + OpenRouter annotations
    sources = _extract_urls(text)
    sources.extend(str(s) for s in payload.get("sources", []) if s)
    if hasattr(message, "annotations") and message.annotations:
        for annotation in message.annotations:
            url = getattr(annotation, "url", None) or getattr(
                getattr(annotation, "url_citation", None), "url", None
            )
            if url:
                sources.append(str(url))

    score = _nearest_score(payload.get("score"))
    contradiction = bool(payload.get("contradiction", False))
    rationale = str(payload.get("rationale") or f"Live benchmark completed via {model}.")
    if not context.profile_resolved:
        rationale = (
            f"Note: '{context.canonical_name}' is not in the local construction peer registry; "
            "benchmarking used the claim/reporting entity name against registry peers. "
            + rationale
        )
    insights = str(payload.get("insights") or "")
    conclusion = str(payload.get("conclusion") or "")
    tldr = str(payload.get("tldr") or "")
    peer_intensity_range = str(payload.get("peer_intensity_range") or "")

    # Build peer intensity table from model response (GHG path only)
    peer_table: list[PeerIntensityRecord] = []
    if ghg:
        raw_peer_data = [r for r in payload.get("peer_data", []) if isinstance(r, dict)]
        for row in raw_peer_data:
            peer_table.append(_peer_record_from_row(row))
        peer_table.sort(
            key=lambda r: (
                0 if r.is_target else 1,
                r.company_name.lower(),
                {"FY2023": 0, "FY2024": 1, "FY2025": 2, "FY2026": 3}.get(r.data_year or "", 99),
            )
        )
        invalid = _invalid_peer_names(
            [r.get("company", "") for r in raw_peer_data],
            context,
        )
        if invalid:
            score = min(score, 0.25)
            rationale = f"Rejected out-of-universe peers: {', '.join(invalid)}. {rationale}"
        if not peer_table and not tldr:
            tldr = (
                "Live search completed but no structured peer intensity rows were returned. "
                "See rationale and evidence snippets below."
            )
    else:
        invalid = _invalid_peer_names(
            [str(n) for n in payload.get("peers_used", []) if n],
            context,
        )
        if invalid:
            score = min(score, 0.25)
            rationale = f"Rejected out-of-universe peers: {', '.join(invalid)}. {rationale}"

    target = context.profile
    header = (
        f"GHG intensity benchmark (unit: {BENCHMARK_UNIT}) | "
        f"Target: {target.company_name} | "
        f"FY2025 Revenue: {target.fy2025_total_revenue}. "
        if ghg and target
        else (f"Peer benchmark | Target: {target.company_name}. " if target else "")
    )

    return BenchmarkEvidence(
        score=score,
        contradiction=contradiction,
        evidence_snippets=[
            str(s).strip()
            for s in payload.get("evidence_snippets", [])
            if str(s).strip()
        ][:4],
        sources=_dedupe(sources)[:6],
        rationale=header + rationale,
        used_live_search=True,
        provider=f"openrouter:{model}",
        peer_context=context,
        peer_intensity_table=peer_table,
        benchmark_unit=BENCHMARK_UNIT if ghg else "varies",
        is_ghg_claim=ghg,
        insights=insights,
        conclusion=conclusion,
        tldr=tldr,
        peer_intensity_range=peer_intensity_range,
    )


# ── Prompt builders ───────────────────────────────────────────────────────────

def _prompt_ghg_intensity(claim: ExtractedClaim, context: ConstructionBenchmarkContext) -> str:
    """GHG intensity benchmark via sustainability reports, FY2023–FY2025."""
    target = context.profile
    claim_year = _claim_fy_year(claim)

    target_block = "Target company: not resolved"
    if target:
        target_block = (
            f"Target company: {target.company_name}\n"
            f"Subsector: {target.subsector_category}\n"
            f"Registry FY2025 revenue (reference): {target.fy2025_total_revenue}"
        )

    company_lines: list[str] = []
    for company in context.all_profiles:
        is_target = target and company.company_name == target.company_name
        rev = company.revenue_rm_million
        rev_note = f"RM {rev:,.1f}M (registry FY2025 ref)" if rev else company.fy2025_total_revenue
        company_lines.append(
            f"  - {company.company_name}{' [TARGET]' if is_target else ''}\n"
            f"    subsector: {company.subsector_category}\n"
            f"    registry_revenue: {rev_note}"
        )
    registry_block = "\n".join(company_lines) or "  - none configured"

    return f"""
You are benchmarking a GHG / carbon ESG claim for a Malaysian construction company.

STANDARD BENCHMARK UNIT: tCO₂e / RM million revenue
  intensity_scope_12 = (Scope 1 + Scope 2 tCO₂e) ÷ revenue (RM million)
  intensity_scope_3  = Scope 3 tCO₂e ÷ revenue (RM million)
  intensity_total    = (Scope 1 + Scope 2 + Scope 3 tCO₂e) ÷ revenue (RM million)

{target_block}

Claim being verified:
- label: {claim.label}
- raw_text: {claim.raw_text}
- metric: {claim.metric}
- achieved_value: {claim.achieved_value}
- target_value: {claim.target_value}
- unit: {claim.unit}
- time_period: {claim.time_period}
- claim reference year: {claim_year or 'unknown'}

ALL Malaysian construction companies in the peer registry (search EVERY company below):
{registry_block}

DATA COLLECTION RULES:
1. For EACH company above, search for their **Sustainability Report** or **ESG Report**
   (NOT the financial/annual report — use sustainability/integrated sustainability disclosures only).
2. For each company, extract for FY2023, FY2024, FY2025 (when published):
   - Scope 1 + Scope 2 total GHG emissions (tCO₂e)
   - Scope 3 total GHG emissions (tCO₂e) — omit row field if not disclosed
   - Total Scope 1+2+3 (tCO₂e) — use reported total if given, else sum S1+2 and S3
3. For each year found, extract that year's revenue (RM million) from the same sustainability
   report or the corresponding annual report revenue note referenced in the sustainability report.
4. Calculate all three intensity metrics per company-year:
   - intensity_scope_12_per_rm_million
   - intensity_scope_3_per_rm_million (null if Scope 3 not disclosed)
   - intensity_total_per_rm_million
5. Return ONE peer_data row per company per year (up to 3 rows per company).
6. Mark is_target=true only for rows belonging to the target company.
7. If a year is not found, omit that row (do not fabricate data).
8. Source must cite the sustainability report name and URL if available.

TARGET COMPANY ROWS:
- For the target company, use the submitted claim values where applicable.
- If the claim states both absolute emissions and intensity, verify they are mathematically consistent.
- Flag internal inconsistency in the rationale if absolute ÷ revenue ≠ stated intensity.

SCORING (use only 0, 0.25, 0.5, 0.75, 1):
- 1.0: Target intensity within peer range for the claim year; 3+ peer year-data points found.
- 0.75: Slightly outside peer range but plausible; or strong data with minor gaps.
- 0.5: Only 1–2 comparable peer year-data points found.
- 0.25: Insufficient sustainability report data across the registry.
- 0.0: Target intensity implausibly low vs all peers (greenwashing signal) or direct contradiction.

Return JSON exactly:
{{
  "score": 0.75,
  "contradiction": false,
  "tldr": "One sentence summary: where the target sits vs peers and whether the claim holds up.",
  "peer_intensity_range": "e.g. S1+2: 2.3–78.3 | S3: 45–210 | Total: 50–280 tCO2e/RM million (FY2023–FY2025)",
  "peer_data": [
    {{
      "company": "Binastra Corporation",
      "data_year": "FY2024",
      "scope_1_2_tco2e": 85000,
      "scope_3_tco2e": 120000,
      "total_scope_123_tco2e": 205000,
      "revenue_rm_million": 920.0,
      "intensity_scope_12_per_rm_million": 92.39,
      "intensity_scope_3_per_rm_million": 130.43,
      "intensity_total_per_rm_million": 222.83,
      "data_found": true,
      "is_target": true,
      "source": "Binastra Sustainability Report 2024 — https://..."
    }},
    {{
      "company": "Sunway Construction",
      "data_year": "FY2024",
      "scope_1_2_tco2e": 12500,
      "scope_3_tco2e": null,
      "total_scope_123_tco2e": 12500,
      "revenue_rm_million": 5100.0,
      "intensity_scope_12_per_rm_million": 2.45,
      "intensity_scope_3_per_rm_million": null,
      "intensity_total_per_rm_million": 2.45,
      "data_found": true,
      "is_target": false,
      "source": "Sunway Construction Sustainability Report 2024 — https://..."
    }}
  ],
  "evidence_snippets": ["max 4 short bullet findings"],
  "sources": ["sustainability report URLs"],
  "rationale": "Detailed scoring explanation (2–3 sentences)",
  "insights": "2–3 sentences on sector trends, data gaps, and how target compares across FY2023–FY2025",
  "conclusion": "One sentence verdict: plausible / aspirational / potential greenwashing"
}}
""".strip()


def _claim_fy_year(claim: ExtractedClaim) -> str | None:
    text = " ".join(filter(None, [claim.time_period, claim.raw_text, claim.label]))
    match = re.search(r"\bFY\s?(20\d{2})\b", text, re.IGNORECASE)
    if match:
        return f"FY{match.group(1)}"
    match = re.search(r"\b(20\d{2})\b", text)
    if match:
        return f"FY{match.group(1)}"
    return None


def _prompt_general(claim: ExtractedClaim, context: ConstructionBenchmarkContext) -> str:
    """General peer comparison prompt for non-GHG ESG claims (safety, water, waste, governance …)."""
    target = context.profile
    target_block = "Target company: not resolved"
    if target:
        target_block = (
            f"Target company: {target.company_name}\n"
            f"Subsector: {target.subsector_category}\n"
            f"Company size: {target.company_size}\n"
            f"FY2025 revenue: {target.fy2025_total_revenue}"
        )

    peer_rows: list[str] = []
    for peer in context.peer_profiles:
        peer_rows.append(
            f"- {peer.company_name} | {peer.subsector_category} | {peer.company_size} | FY2025 revenue: {peer.fy2025_total_revenue}"
        )
    peer_block = "\n".join(peer_rows) or "- none configured"

    return f"""
You are benchmarking an ESG claim for a Malaysian construction company against industry peers.
Use live web evidence. Return ONLY JSON.

{target_block}

Claim:
- label: {claim.label}
- raw_text: {claim.raw_text}
- pillar: {claim.pillar}
- metric: {claim.metric}
- achieved_value: {claim.achieved_value}
- target_value: {claim.target_value}
- unit: {claim.unit}
- time_period: {claim.time_period}
- entity: {claim.entity}

Malaysian construction peer universe (ONLY compare against these companies):
{peer_block}

Tasks:
1. Search for the same ESG metric/indicator for as many peers as possible.
2. Determine whether the claim value is plausible vs. the peer range.
3. Detect contradiction if credible public evidence conflicts with the claim.
4. Score using only: 0, 0.25, 0.5, 0.75, 1.

Score rubric:
- 1.0: claim within plausible peer range, well-supported data.
- 0.75: claim outside range but not contradicted.
- 0.5: partial/limited peer data found.
- 0.25: very weak peer evidence.
- 0.0: direct contradiction or implausible claim vs. all peers.

Hard rules:
- Only use companies from the peer universe above.
- Do not use cement manufacturers, plantations, utilities, telcos, or banks as peers.

Return JSON exactly:
{{
  "score": 0.75,
  "contradiction": false,
  "peers_used": ["Peer Company Name"],
  "evidence_snippets": ["short evidence sentence"],
  "sources": ["URL or report name"],
  "rationale": "one concise explanation"
}}
""".strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_ghg_claim(claim: ExtractedClaim) -> bool:
    text = " ".join(filter(None, [claim.raw_text, claim.metric, claim.category, claim.unit, claim.label]))
    return bool(_GHG_KEYWORDS.search(text))


def _invalid_peer_names(
    names: list[Any],
    context: ConstructionBenchmarkContext,
) -> list[str]:
    if not names:
        return []
    allowed = {_norm(n) for n in context.allowed_peer_names}
    allowed.add(_norm(context.canonical_name))
    return [str(n) for n in names if _norm(str(n)) not in allowed and str(n).strip()]


def _norm(value: str) -> str:
    cleaned = value.lower().strip()
    for suffix in (" berhad", " bhd", " sdn bhd", " group", " corporation"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return re.sub(r"[^a-z0-9]+", "", cleaned)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _intensity_per_rm_million(
    emissions: float | None,
    revenue: float | None,
) -> float | None:
    if emissions is None or revenue is None or revenue <= 0:
        return None
    return round(emissions / revenue, 4)


def _normalize_data_year(raw: Any) -> str | None:
    raw_year = str(raw or "").strip()
    if raw_year.lower() in ("none", "null", ""):
        return None
    return raw_year


def _peer_record_from_row(row: dict[str, Any]) -> PeerIntensityRecord:
    rev = _float_or_none(row.get("revenue_rm_million"))
    s12 = _float_or_none(row.get("scope_1_2_tco2e"))
    s3 = _float_or_none(row.get("scope_3_tco2e"))
    total = _float_or_none(row.get("total_scope_123_tco2e"))
    if total is None:
        if s12 is not None and s3 is not None:
            total = s12 + s3
        elif s12 is not None:
            total = s12

    i12 = _float_or_none(row.get("intensity_scope_12_per_rm_million"))
    if i12 is None:
        i12 = _float_or_none(row.get("intensity_tco2e_per_rm_million"))
    if i12 is None:
        i12 = _intensity_per_rm_million(s12, rev)

    i3 = _float_or_none(row.get("intensity_scope_3_per_rm_million"))
    if i3 is None:
        i3 = _intensity_per_rm_million(s3, rev)

    itotal = _float_or_none(row.get("intensity_total_per_rm_million"))
    if itotal is None:
        itotal = _intensity_per_rm_million(total, rev)

    return PeerIntensityRecord(
        company_name=str(row.get("company", "")),
        revenue_rm_million=rev,
        scope_1_2_tco2e=s12,
        scope_3_tco2e=s3,
        total_scope_123_tco2e=total,
        intensity_scope_12=i12,
        intensity_scope_3=i3,
        intensity_total=itotal,
        data_year=_normalize_data_year(row.get("data_year")),
        data_found=bool(row.get("data_found", False)),
        source=str(row.get("source", "web search")),
        is_target=bool(row.get("is_target", False)),
    )


def _parse_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned) if isinstance(json.loads(cleaned), dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


def _nearest_score(value: Any) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.25
    return min(ALLOWED_SCORES, key=lambda s: abs(s - raw))


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_RE.findall(text):
        parsed = urlparse(match.rstrip(".,;)"))
        if parsed.scheme and parsed.netloc:
            urls.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}")
    return urls


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
