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
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlparse

from config import settings
from models.schemas import ExtractedClaim
from providers.construction_peer_registry import (
    ConstructionBenchmarkContext,
    resolve_benchmark_context,
)
from providers.jobstreet_peer_registry import (
    JobstreetCompanyReview,
    jobstreet_peers_for_target,
    match_jobstreet_to_construction_profile,
    resolve_jobstreet_for_company,
)

logger = logging.getLogger("greengag.openrouter_benchmark")

ALLOWED_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
URL_RE = re.compile(r"https?://[^\s\])\"']+")
YEAR_RANK = {"FY2023": 0, "FY2024": 1, "FY2025": 2, "FY2026": 3}

# Keywords that mark a claim as GHG / carbon-related
_GHG_KEYWORDS = re.compile(
    r"\b(ghg|greenhouse|co2|co₂|carbon|scope\s*[123]|emission|tco2|tco₂|decarboni[sz]|net.?zero|climate)\b",
    re.IGNORECASE,
)

_SOCIAL_KEYWORDS = re.compile(
    r"\b(training|employee|workforce|safety|health|diversity|labour|labor|human rights|"
    r"community|worker|staff|working environment|occupational|anti-corruption|grievance|"
    r"hours|satisfaction|wellbeing|well-being|injury|ltifr|trifr)\b",
    re.IGNORECASE,
)

BENCHMARK_UNIT = "tCO₂e / RM million revenue"
OPENROUTER_BENCHMARK_MODEL = "google/gemini-2.5-flash"


@dataclass(frozen=True)
class PeerIntensityRecord:
    company_name: str
    revenue_rm_million: float | None
    scope_1_2_tco2e: float | None
    intensity: float | None
    scope_3_included: bool = False
    emissions_note: str = ""
    data_year: str | None = None
    data_found: bool = False
    source: str = ""
    is_target: bool = False


@dataclass(frozen=True)
class JobstreetSampleReviewRecord:
    review_date: str
    role: str
    rating: float | None = None
    positive: str = ""
    negative: str = ""
    tenure: str = ""


@dataclass(frozen=True)
class JobstreetReviewRecord:
    company_name: str
    overall_rating: float | None
    review_count: int | None
    work_life_balance: float | None
    career_development: float | None
    working_environment: float | None
    recommend_pct: float | None
    ai_summary: str
    jobstreet_url: str
    timeline_note: str = ""
    trend_summary: str = ""
    sample_reviews: list[JobstreetSampleReviewRecord] = field(default_factory=list)
    is_target: bool = False


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
    jobstreet_table: list[JobstreetReviewRecord] = field(default_factory=list)
    benchmark_unit: str = BENCHMARK_UNIT
    is_ghg_claim: bool = False
    is_social_claim: bool = False
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
    social = _is_social_claim(claim)
    model = settings.openrouter_online_model
    if OPENROUTER_BENCHMARK_MODEL not in model:
        logger.warning(
            "OPENROUTER_MODEL=%s; expected %s via OpenRouter (no direct Google Gemini).",
            model,
            OPENROUTER_BENCHMARK_MODEL,
        )
    if ghg:
        prompt = _prompt_ghg_intensity(claim, context)
        system_msg = (
            "You are an ESG auditor benchmarking Malaysian construction companies. "
            "Search sustainability/ESG reports for Scope 1+2 GHG emissions only. "
            "If a report bundles Scope 3 into the figure, flag scope_3_included=true. "
            "Return ONLY valid JSON."
        )
    elif social:
        prompt = _prompt_social_jobstreet(claim, context)
        system_msg = (
            "You are an ESG auditor benchmarking social/working-environment claims for "
            "Malaysian construction companies. Scrape the Jobstreet review pages provided "
            "and compare employee sentiment vs the claim. Return ONLY valid JSON."
        )
    else:
        prompt = _prompt_general(claim, context)
        system_msg = (
            "You are an ESG auditor benchmarking Malaysian construction companies. "
            "Use live web evidence. Return ONLY valid JSON."
        )

    try:
        client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_msg},
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
    jobstreet_table: list[JobstreetReviewRecord] = []
    if ghg:
        raw_peer_data = [r for r in payload.get("peer_data", []) if isinstance(r, dict)]
        for row in raw_peer_data:
            peer_table.append(_peer_record_from_row(row))
        peer_table = _latest_peer_rows_by_company(peer_table)
        peer_table.sort(
            key=lambda r: (
                0 if r.is_target else 1,
                r.company_name.lower(),
                -YEAR_RANK.get(r.data_year or "", -1),
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
    elif social:
        raw_js = [r for r in payload.get("jobstreet_data", []) if isinstance(r, dict)]
        for row in raw_js:
            jobstreet_table.append(_jobstreet_record_from_row(row))
        if not jobstreet_table:
            target_name = context.profile.company_name if context.profile else context.canonical_name
            jobstreet_table = _local_jobstreet_baseline(target_name, context)
        jobstreet_table = _enrich_jobstreet_from_local(jobstreet_table)
        jobstreet_table.sort(key=lambda r: (0 if r.is_target else 1, r.company_name.lower()))
        if not tldr:
            tldr = "Jobstreet employee review benchmark for working environment and social claims."
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
        else (
            f"Jobstreet social benchmark | Target: {target.company_name}. "
            if social and target
            else (f"Peer benchmark | Target: {target.company_name}. " if target else "")
        )
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
        jobstreet_table=jobstreet_table,
        benchmark_unit=BENCHMARK_UNIT if ghg else ("Jobstreet rating (1–5)" if social else "varies"),
        is_ghg_claim=ghg,
        is_social_claim=social,
        insights=insights,
        conclusion=conclusion,
        tldr=tldr,
        peer_intensity_range=peer_intensity_range,
    )


# ── Prompt builders ───────────────────────────────────────────────────────────

def _prompt_ghg_intensity(claim: ExtractedClaim, context: ConstructionBenchmarkContext) -> str:
    """GHG intensity benchmark via latest sustainability reports."""
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

STANDARD BENCHMARK UNIT: tCO₂e / RM million revenue (Scope 1 + Scope 2 ONLY)
  intensity = (Scope 1 + Scope 2 tCO₂e) ÷ revenue (RM million)

IMPORTANT: Do NOT report separate Scope 3 columns. If the sustainability report's
"Scope 1+2" figure actually bundles Scope 3, set scope_3_included=true and
emissions_note="(Scope 3 included)" on that row.

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
1. For EACH company above, search for their latest **Sustainability Report** or **ESG Report**
   (NOT the financial/annual report alone — use sustainability/integrated sustainability disclosures).
2. Prioritise the newest disclosed year in this order: FY2026, FY2025, FY2024, then FY2023.
   - Prefer FY2025/FY2026 where available.
   - Do NOT return an older FY2023 row when FY2024/FY2025/FY2026 is available.
   - Use FY2023 only as a last resort and say in emissions_note that newer data was not found.
3. For EACH company, return exactly ONE peer_data row: the latest available Scope 1+2 row.
4. Extract Scope 1 + Scope 2 total GHG emissions (tCO₂e) and matching year revenue (RM million).
5. Calculate intensity_tco2e_per_rm_million = scope_1_2_tco2e ÷ revenue_rm_million.
6. If Scope 3 is bundled into the reported figure, set scope_3_included=true and emissions_note="(Scope 3 included)".
7. If Scope 1+2 data cannot be found for a company after searching its latest reports, still return a row:
   - data_found=false
   - data_year=null
   - numeric fields null
   - emissions_note="Latest Scope 1+2 GHG data not found in FY2025/FY2026 sustainability report search"
   - source should mention the searched report/page if known.
8. Mark is_target=true only for rows belonging to the target company.
9. Source must cite the sustainability report name and URL if available.

TARGET COMPANY ROWS:
- For the target company, use the submitted claim values where applicable.
- If the claim states both absolute emissions and intensity, verify they are mathematically consistent.
- Flag internal inconsistency in the rationale if absolute ÷ revenue ≠ stated intensity.

SCORING (use only 0, 0.25, 0.5, 0.75, 1):
- 1.0: Target intensity within latest peer range; 3+ latest peer data points found.
- 0.75: Slightly outside peer range but plausible; or strong data with minor gaps.
- 0.5: Only 1–2 comparable peer year-data points found.
- 0.25: Insufficient sustainability report data across the registry.
- 0.0: Target intensity implausibly low vs all peers (greenwashing signal) or direct contradiction.

Return JSON exactly:
{{
  "score": 0.75,
  "contradiction": false,
  "tldr": "One sentence summary: where the target sits vs peers and whether the claim holds up.",
  "peer_intensity_range": "e.g. 2.3–8.4 tCO2e/RM million S1+2 (latest FY2025/FY2026 where available)",
  "peer_data": [
    {{
      "company": "Binastra Corporation",
      "data_year": "FY2026",
      "scope_1_2_tco2e": 4256.1,
      "revenue_rm_million": 946.6,
      "intensity_tco2e_per_rm_million": 4.5,
      "scope_3_included": false,
      "emissions_note": "",
      "data_found": true,
      "is_target": true,
      "source": "Binastra Sustainability Report 2024 — https://..."
    }},
    {{
      "company": "Sunway Construction",
      "data_year": null,
      "scope_1_2_tco2e": null,
      "revenue_rm_million": null,
      "intensity_tco2e_per_rm_million": null,
      "scope_3_included": false,
      "emissions_note": "Latest Scope 1+2 GHG data not found in FY2025/FY2026 sustainability report search",
      "data_found": false,
      "is_target": false,
      "source": "Searched Sunway Construction FY2025/FY2026 Sustainability Report"
    }}
  ],
  "evidence_snippets": ["max 4 short bullet findings"],
  "sources": ["sustainability report URLs"],
  "rationale": "Detailed scoring explanation (2–3 sentences)",
  "insights": "2–3 sentences on latest-year sector trends, data gaps, and how target compares against peers",
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


def _prompt_social_jobstreet(claim: ExtractedClaim, context: ConstructionBenchmarkContext) -> str:
    """Social / working-environment benchmark via Jobstreet employee reviews."""
    target = context.profile
    target_name = target.company_name if target else context.canonical_name

    js_lines: list[str] = []
    for review in jobstreet_peers_for_target(target_name):
        is_target = _norm(review.company_name) == _norm(target_name)
        baseline = (
            f"overall={review.overall_rating}, reviews={review.review_count}, "
            f"working_env={review.working_environment}, recommend={review.recommend_pct}%"
            if review.overall_rating is not None
            else "baseline pending live scrape"
        )
        js_lines.append(
            f"  - {review.company_name}{' [TARGET]' if is_target else ''}\n"
            f"    Jobstreet URL: {review.jobstreet_url}\n"
            f"    Local baseline: {baseline}\n"
            f"    Summary: {review.ai_summary[:200] if review.ai_summary else 'n/a'}"
        )
    jobstreet_block = "\n".join(js_lines) or "  - none configured"

    target_block = f"Target company: {target_name}"
    if target:
        target_block += f"\nSubsector: {target.subsector_category}"

    return f"""
You are benchmarking a SOCIAL (S pillar) ESG claim for a Malaysian construction company
using Jobstreet employee reviews about working environment, culture, training, and safety.

{target_block}

Claim being verified:
- label: {claim.label}
- raw_text: {claim.raw_text}
- pillar: {claim.pillar}
- metric: {claim.metric}
- achieved_value: {claim.achieved_value}
- unit: {claim.unit}
- time_period: {claim.time_period}

JOBSTREET PEER REVIEW PAGES (scrape EVERY URL below):
{jobstreet_block}

TASKS:
1. Visit each Jobstreet reviews URL and extract: overall rating (1–5), review count,
   work/life balance, career development, working environment, % recommend to friends.
2. For EACH company, pick 3–5 individual employee reviews dated between 2020 and 2026
   (include at least one from 2024–2026 if available, and one older review for trend).
   Extract review_date (YYYY-MM), role, rating, tenure, positive themes, negative themes.
3. Write timeline_note: warn that older reviews (e.g. 2020–2023) may not reflect culture
   changes claimed in 2025+ sustainability reports — weight recent reviews higher.
4. Write trend_summary: AI summary of how sentiment evolved across the sampled years.
5. Compare the target company's employee sentiment vs peers for the claim topic
   (e.g. training hours, safety culture, employee satisfaction, working environment).
6. Flag contradiction if the claim strongly conflicts with employee review themes.
7. Score using only: 0, 0.25, 0.5, 0.75, 1.

Return JSON exactly:
{{
  "score": 0.75,
  "contradiction": false,
  "tldr": "One sentence: how employee reviews align or conflict with the social claim.",
  "jobstreet_data": [
    {{
      "company": "Gamuda Berhad",
      "overall_rating": 4.2,
      "review_count": 103,
      "work_life_balance": 3.7,
      "career_development": 4.0,
      "working_environment": 4.0,
      "recommend_pct": 76,
      "ai_summary": "Brief employee sentiment summary from Jobstreet.",
      "timeline_note": "Reviews span 2019–2025. Weight 2024–2025 reviews higher than pre-2023 posts.",
      "trend_summary": "How sentiment changed across sampled years.",
      "sample_reviews": [
        {{
          "review_date": "2025-03",
          "role": "Health and Safety Officer",
          "rating": 5.0,
          "tenure": "Less than 1 year, former employee",
          "positive": "Great career growth and positive work culture.",
          "negative": "High expectations and tight deadlines."
        }}
      ],
      "jobstreet_url": "https://my.jobstreet.com/companies/gamuda-group-168553946574107/reviews",
      "is_target": false
    }}
  ],
  "evidence_snippets": ["max 4 short findings from Jobstreet reviews"],
  "sources": ["Jobstreet review URLs"],
  "rationale": "Scoring explanation (2–3 sentences)",
  "insights": "Sector social/working-environment trends from reviews",
  "conclusion": "One sentence verdict on claim credibility vs employee sentiment"
}}
""".strip()


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


def _is_social_claim(claim: ExtractedClaim) -> bool:
    if _is_ghg_claim(claim):
        return False
    pillar = (claim.pillar or "").strip().lower()
    if pillar in ("social", "s", "people"):
        return True
    text = " ".join(filter(None, [claim.raw_text, claim.metric, claim.category, claim.label]))
    return bool(_SOCIAL_KEYWORDS.search(text))


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
    scope_3_included = bool(row.get("scope_3_included", False))
    emissions_note = str(row.get("emissions_note") or "").strip()
    if scope_3_included and not emissions_note:
        emissions_note = "(Scope 3 included)"

    intensity = _float_or_none(row.get("intensity_tco2e_per_rm_million"))
    if intensity is None:
        intensity = _float_or_none(row.get("intensity_scope_12_per_rm_million"))
    if intensity is None:
        intensity = _intensity_per_rm_million(s12, rev)

    return PeerIntensityRecord(
        company_name=str(row.get("company", "")),
        revenue_rm_million=rev,
        scope_1_2_tco2e=s12,
        intensity=intensity,
        scope_3_included=scope_3_included,
        emissions_note=emissions_note,
        data_year=_normalize_data_year(row.get("data_year")),
        data_found=bool(row.get("data_found", False)),
        source=str(row.get("source", "web search")),
        is_target=bool(row.get("is_target", False)),
    )


def _latest_peer_rows_by_company(
    rows: list[PeerIntensityRecord],
) -> list[PeerIntensityRecord]:
    """Keep one latest row per company, preferring disclosed FY2025/FY2026 data."""
    latest: dict[str, PeerIntensityRecord] = {}
    for row in rows:
        key = _norm(row.company_name)
        if not key:
            continue
        existing = latest.get(key)
        if existing is None:
            latest[key] = row
            continue

        row_rank = YEAR_RANK.get(row.data_year or "", -1)
        existing_rank = YEAR_RANK.get(existing.data_year or "", -1)
        row_score = (1 if row.data_found else 0, row_rank)
        existing_score = (1 if existing.data_found else 0, existing_rank)
        if row_score > existing_score:
            latest[key] = row

    out: list[PeerIntensityRecord] = []
    for row in latest.values():
        if row.data_found and row.data_year == "FY2023" and not row.emissions_note:
            row = replace(
                row,
                emissions_note="Latest available row is FY2023; FY2025/FY2026 Scope 1+2 data not found",
            )
        out.append(row)
    return out


def _jobstreet_record_from_row(row: dict[str, Any]) -> JobstreetReviewRecord:
    return JobstreetReviewRecord(
        company_name=str(row.get("company", "")),
        overall_rating=_float_or_none(row.get("overall_rating")),
        review_count=_int_or_none(row.get("review_count")),
        work_life_balance=_float_or_none(row.get("work_life_balance")),
        career_development=_float_or_none(row.get("career_development")),
        working_environment=_float_or_none(row.get("working_environment")),
        recommend_pct=_float_or_none(row.get("recommend_pct")),
        ai_summary=str(row.get("ai_summary") or ""),
        jobstreet_url=str(row.get("jobstreet_url") or ""),
        timeline_note=str(row.get("timeline_note") or ""),
        trend_summary=str(row.get("trend_summary") or ""),
        sample_reviews=_sample_reviews_from_row(row.get("sample_reviews")),
        is_target=bool(row.get("is_target", False)),
    )


def _sample_reviews_from_row(raw: Any) -> list[JobstreetSampleReviewRecord]:
    if not isinstance(raw, list):
        return []
    out: list[JobstreetSampleReviewRecord] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        date = str(item.get("review_date") or item.get("date") or "").strip()
        role = str(item.get("role") or "").strip()
        if not date and not role:
            continue
        out.append(
            JobstreetSampleReviewRecord(
                review_date=date,
                role=role,
                rating=_float_or_none(item.get("rating")),
                positive=str(item.get("positive") or item.get("pros") or "").strip(),
                negative=str(item.get("negative") or item.get("cons") or "").strip(),
                tenure=str(item.get("tenure") or "").strip(),
            )
        )
    return out


def _sample_reviews_from_local(reviews: list[JobstreetSampleReview]) -> list[JobstreetSampleReviewRecord]:
    return [
        JobstreetSampleReviewRecord(
            review_date=r.review_date,
            role=r.role,
            rating=r.rating,
            positive=r.positive,
            negative=r.negative,
            tenure=r.tenure,
        )
        for r in reviews
    ]


def _enrich_jobstreet_from_local(rows: list[JobstreetReviewRecord]) -> list[JobstreetReviewRecord]:
    enriched: list[JobstreetReviewRecord] = []
    for row in rows:
        local = resolve_jobstreet_for_company(row.company_name)
        if not local:
            enriched.append(row)
            continue
        enriched.append(
            replace(
                row,
                timeline_note=row.timeline_note or local.timeline_note,
                trend_summary=row.trend_summary or local.trend_summary,
                sample_reviews=row.sample_reviews or _sample_reviews_from_local(local.sample_reviews),
                ai_summary=row.ai_summary or local.ai_summary,
            )
        )
    return enriched


def _local_jobstreet_baseline(
    target_name: str,
    context: ConstructionBenchmarkContext,
) -> list[JobstreetReviewRecord]:
    rows: list[JobstreetReviewRecord] = []
    for review in jobstreet_peers_for_target(target_name):
        is_target = _norm(review.company_name) == _norm(target_name)
        if context.profile and not is_target:
            matched = match_jobstreet_to_construction_profile(context.profile.company_name)
            if matched and _norm(matched.company_name) == _norm(review.company_name):
                is_target = True
        rows.append(
            JobstreetReviewRecord(
                company_name=review.company_name,
                overall_rating=review.overall_rating,
                review_count=review.review_count,
                work_life_balance=review.work_life_balance,
                career_development=review.career_development,
                working_environment=review.working_environment,
                recommend_pct=review.recommend_pct,
                ai_summary=review.ai_summary,
                jobstreet_url=review.jobstreet_url,
                timeline_note=review.timeline_note,
                trend_summary=review.trend_summary,
                sample_reviews=_sample_reviews_from_local(review.sample_reviews),
                is_target=is_target,
            )
        )
    return rows


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
