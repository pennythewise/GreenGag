"""Local Jobstreet employee-review registry for Malaysian construction peer benchmarking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from providers.construction_peer_registry import _match_company, _normalize as _norm

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "jobstreet_company_reviews.json"


@dataclass(frozen=True)
class JobstreetSampleReview:
    review_date: str
    role: str
    rating: float | None = None
    positive: str = ""
    negative: str = ""
    tenure: str = ""


@dataclass(frozen=True)
class JobstreetCompanyReview:
    company_name: str
    jobstreet_url: str
    overall_rating: float | None = None
    review_count: int | None = None
    recommend_pct: float | None = None
    salary_high_or_average_pct: float | None = None
    work_life_balance: float | None = None
    career_development: float | None = None
    benefits_perks: float | None = None
    management: float | None = None
    working_environment: float | None = None
    diversity_equal_opportunity: float | None = None
    ai_summary: str = ""
    timeline_note: str = ""
    trend_summary: str = ""
    sample_reviews: list[JobstreetSampleReview] = field(default_factory=list)
    sample_themes_positive: list[str] = field(default_factory=list)
    sample_themes_negative: list[str] = field(default_factory=list)


def load_jobstreet_reviews() -> list[JobstreetCompanyReview]:
    registry = _load_registry()
    reviews: list[JobstreetCompanyReview] = []
    for row in registry.get("companies") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("company_name") or "").strip()
        url = str(row.get("jobstreet_url") or "").strip()
        if not name or not url:
            continue
        dims = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
        reviews.append(
            JobstreetCompanyReview(
                company_name=name,
                jobstreet_url=url,
                overall_rating=_float_or_none(row.get("overall_rating")),
                review_count=_int_or_none(row.get("review_count")),
                recommend_pct=_float_or_none(row.get("recommend_pct")),
                salary_high_or_average_pct=_float_or_none(row.get("salary_high_or_average_pct")),
                work_life_balance=_float_or_none(dims.get("work_life_balance")),
                career_development=_float_or_none(dims.get("career_development")),
                benefits_perks=_float_or_none(dims.get("benefits_perks")),
                management=_float_or_none(dims.get("management")),
                working_environment=_float_or_none(dims.get("working_environment")),
                diversity_equal_opportunity=_float_or_none(dims.get("diversity_equal_opportunity")),
                ai_summary=str(row.get("ai_summary") or ""),
                timeline_note=str(row.get("timeline_note") or ""),
                trend_summary=str(row.get("trend_summary") or ""),
                sample_reviews=_parse_sample_reviews(row.get("sample_reviews")),
                sample_themes_positive=[
                    str(t) for t in (row.get("sample_themes_positive") or []) if str(t).strip()
                ],
                sample_themes_negative=[
                    str(t) for t in (row.get("sample_themes_negative") or []) if str(t).strip()
                ],
            )
        )
    return reviews


def resolve_jobstreet_for_company(name: str | None) -> JobstreetCompanyReview | None:
    if not name:
        return None
    query = _norm(name)
    for review in load_jobstreet_reviews():
        if _norm(review.company_name) == query:
            return review
        # Binastra Construction (Jobstreet) ↔ Binastra Corporation (registry)
        if "binastra" in query and "binastra" in _norm(review.company_name):
            return review
    return None


def jobstreet_peers_for_target(target_name: str | None) -> list[JobstreetCompanyReview]:
    """All Jobstreet profiles except target (target first when matched)."""
    reviews = load_jobstreet_reviews()
    if not target_name:
        return reviews
    matched = resolve_jobstreet_for_company(target_name)
    if not matched:
        return reviews
    peers = [r for r in reviews if _norm(r.company_name) != _norm(matched.company_name)]
    return [matched, *peers]


def match_jobstreet_to_construction_profile(company_name: str) -> JobstreetCompanyReview | None:
    """Fuzzy match a construction registry name to a Jobstreet entry."""
    reviews = load_jobstreet_reviews()
    names = [r.company_name for r in reviews]
    from providers.construction_peer_registry import CompanyProfile

    fake_profiles = [
        CompanyProfile(company_name=n, subsector_category="", company_size="", fy2025_total_revenue="")
        for n in names
    ]
    matched = _match_company(fake_profiles, company_name)
    if not matched:
        return resolve_jobstreet_for_company(company_name)
    return resolve_jobstreet_for_company(matched.company_name)


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_sample_reviews(raw: Any) -> list[JobstreetSampleReview]:
    if not isinstance(raw, list):
        return []
    reviews: list[JobstreetSampleReview] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        date = str(item.get("review_date") or item.get("date") or "").strip()
        role = str(item.get("role") or "").strip()
        if not date and not role:
            continue
        reviews.append(
            JobstreetSampleReview(
                review_date=date,
                role=role,
                rating=_float_or_none(item.get("rating")),
                positive=str(item.get("positive") or item.get("pros") or "").strip(),
                negative=str(item.get("negative") or item.get("cons") or "").strip(),
                tenure=str(item.get("tenure") or "").strip(),
            )
        )
    return reviews


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
