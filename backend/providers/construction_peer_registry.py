"""Local registry of Malaysian construction company profiles for peer benchmarking."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "construction_company_profiles.json"

NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
# Matches patterns like "RM5.34 Billion", "RM916.9 Million", "RM1.50B"
_REVENUE_RE = re.compile(
    r"(?:RM)?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|b|m)\b",
    re.IGNORECASE,
)


def parse_revenue_rm_million(revenue_str: str) -> float | None:
    """Convert a human-readable revenue string to RM millions (float).

    Examples
    --------
    "RM5.34 Billion"  -> 5340.0
    "RM916.9 Million" -> 916.9
    "RM1.50B"         -> 1500.0
    """
    m = _REVENUE_RE.search(revenue_str)
    if not m:
        return None
    raw = float(m.group(1).replace(",", ""))
    unit = m.group(2).lower()
    if unit in ("billion", "b"):
        return round(raw * 1_000.0, 2)
    return round(raw, 2)  # already millions


@dataclass(frozen=True)
class CompanyProfile:
    company_name: str
    subsector_category: str
    company_size: str
    fy2025_total_revenue: str          # human-readable display string

    @property
    def revenue_rm_million(self) -> float | None:
        """FY2025 revenue parsed to RM millions; None when unparseable."""
        return parse_revenue_rm_million(self.fy2025_total_revenue)


@dataclass(frozen=True)
class ConstructionBenchmarkContext:
    profile: CompanyProfile | None
    peer_profiles: list[CompanyProfile] = field(default_factory=list)
    country: str = "Malaysia"
    sector: str = "construction"
    profile_resolved: bool = False
    resolution_source: str | None = None

    @property
    def all_profiles(self) -> list[CompanyProfile]:
        """Full registry list with target company first when resolved."""
        if not self.profile:
            return list(self.peer_profiles)
        return [self.profile, *self.peer_profiles]

    @property
    def canonical_name(self) -> str:
        return self.profile.company_name if self.profile else "Unknown company"

    @property
    def allowed_peer_names(self) -> list[str]:
        return [p.company_name for p in self.all_profiles]


def resolve_benchmark_context(
    *,
    reporting_entity: str | None = None,
    claim_entity: str | None = None,
) -> ConstructionBenchmarkContext:
    registry = _load_registry()
    sector = str(registry.get("sector", "construction"))
    country = str(registry.get("country", "Malaysia"))
    companies = _company_profiles(registry)

    for label, candidate in (
        ("claim_entity", claim_entity),
        ("reporting_entity", reporting_entity),
    ):
        if not candidate:
            continue
        matched = _match_company(companies, candidate)
        if matched:
            peers = [p for p in companies if p.company_name != matched.company_name]
            return ConstructionBenchmarkContext(
                profile=matched,
                peer_profiles=peers,
                country=country,
                sector=sector,
                profile_resolved=True,
                resolution_source=label,
            )

    fallback_name = (claim_entity or reporting_entity or "Unknown company").strip()
    return ConstructionBenchmarkContext(
        profile=CompanyProfile(
            company_name=fallback_name,
            subsector_category="",
            company_size="",
            fy2025_total_revenue="",
        ),
        peer_profiles=companies,
        country=country,
        sector=sector,
        profile_resolved=False,
        resolution_source=None,
    )


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _company_profiles(registry: dict[str, Any]) -> list[CompanyProfile]:
    profiles: list[CompanyProfile] = []
    for row in registry.get("companies") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("company_name") or "").strip()
        if not name:
            continue
        profiles.append(
            CompanyProfile(
                company_name=name,
                subsector_category=str(row.get("subsector_category") or ""),
                company_size=str(row.get("company_size") or ""),
                fy2025_total_revenue=str(row.get("fy2025_total_revenue") or ""),
            )
        )
    return profiles


def _match_company(
    companies: list[CompanyProfile], raw_name: str
) -> CompanyProfile | None:
    normalized_query = _normalize(raw_name)
    if not normalized_query:
        return None
    for profile in companies:
        normalized_name = _normalize(profile.company_name)
        if not normalized_name:
            continue
        if (
            normalized_query == normalized_name
            or normalized_query in normalized_name
            or normalized_name in normalized_query
        ):
            return profile
    return None


def _normalize(value: str) -> str:
    cleaned = value.lower().strip()
    for suffix in (" berhad", " bhd", " sdn bhd", " sdn. bhd.", " group", " corporation"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return NORMALIZE_RE.sub("", cleaned)
