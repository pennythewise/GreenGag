"""Local registry of Malaysian construction company profiles and peer universes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "construction_company_profiles.json"

NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ConstructionBenchmarkContext:
    profile_key: str | None
    canonical_name: str
    country: str
    sector: str
    subsector: str | None
    products_services: list[str] = field(default_factory=list)
    allowed_peer_names: list[str] = field(default_factory=list)
    excluded_peer_categories: list[str] = field(default_factory=list)
    profile_resolved: bool = False
    resolution_source: str | None = None


def resolve_benchmark_context(
    *,
    reporting_entity: str | None = None,
    claim_entity: str | None = None,
) -> ConstructionBenchmarkContext:
    registry = _load_registry()
    sector = str(registry.get("sector", "construction"))
    country = str(registry.get("country", "Malaysia"))
    default_excluded = list(registry.get("default_excluded_peer_categories") or [])

    for label, candidate in (
        ("claim_entity", claim_entity),
        ("reporting_entity", reporting_entity),
    ):
        if not candidate:
            continue
        profile_key, profile = _match_company(registry, candidate)
        if profile:
            return _context_from_profile(
                profile_key=profile_key,
                profile=profile,
                registry=registry,
                sector=sector,
                country=country,
                default_excluded=default_excluded,
                resolution_source=label,
            )

    fallback_name = (claim_entity or reporting_entity or "Unknown company").strip()
    return ConstructionBenchmarkContext(
        profile_key=None,
        canonical_name=fallback_name,
        country=country,
        sector=sector,
        subsector=None,
        excluded_peer_categories=default_excluded,
        profile_resolved=False,
        resolution_source=None,
    )


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _match_company(
    registry: dict[str, Any], raw_name: str
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    companies: dict[str, Any] = registry.get("companies") or {}
    normalized_query = _normalize(raw_name)
    if not normalized_query:
        return None, None

    for key, profile in companies.items():
        names = [profile.get("canonical_name", ""), *profile.get("aliases", []), key]
        for name in names:
            normalized_name = _normalize(str(name))
            if not normalized_name:
                continue
            if normalized_query == normalized_name or normalized_query in normalized_name or normalized_name in normalized_query:
                return key, profile
    return None, None


def _context_from_profile(
    *,
    profile_key: str,
    profile: dict[str, Any],
    registry: dict[str, Any],
    sector: str,
    country: str,
    default_excluded: list[str],
    resolution_source: str,
) -> ConstructionBenchmarkContext:
    companies: dict[str, Any] = registry.get("companies") or {}
    peer_keys = profile.get("allowed_peers") or []
    peer_names: list[str] = []
    seen: set[str] = set()
    for peer_key in peer_keys:
        peer = companies.get(peer_key)
        if not peer:
            continue
        name = str(peer.get("canonical_name") or peer_key)
        if name not in seen:
            seen.add(name)
            peer_names.append(name)

    return ConstructionBenchmarkContext(
        profile_key=profile_key,
        canonical_name=str(profile.get("canonical_name") or profile_key),
        country=country,
        sector=sector,
        subsector=profile.get("subsector"),
        products_services=[str(item) for item in profile.get("products_services") or []],
        allowed_peer_names=peer_names,
        excluded_peer_categories=default_excluded,
        profile_resolved=True,
        resolution_source=resolution_source,
    )


def _normalize(value: str) -> str:
    cleaned = value.lower().strip()
    for suffix in (" berhad", " bhd", " sdn bhd", " sdn. bhd.", " group"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return NORMALIZE_RE.sub("", cleaned)
