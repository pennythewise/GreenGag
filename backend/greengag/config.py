"""Environment & secrets binding with startup validation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("greengag.config")

# Full live audit (all agents + external APIs).
REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "Core orchestration": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
    "Remote sensing": (
        "PLANET_LABS_API_KEY",
        "SENTINEL_HUB_CLIENT_ID",
        "SENTINEL_HUB_CLIENT_SECRET",
        "GOOGLE_EARTH_ENGINE_CREDENTIALS",
    ),
    "External data": ("NEWS_API_KEY", "INTERNAL_LEDGER_DB_URL"),
}

# Report Parser ingest + extract pipeline (RAG + Claude).
PIPELINE_KEYS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)


@dataclass(frozen=True)
class Settings:
    data_mode: str
    keys: dict[str, str | None]
    embedding_model: str
    embedding_dimensions: int
    rag_similarity_threshold: float
    rag_top_k_per_pillar: int
    rag_max_chunks_to_llm: int
    llm_extraction_model: str

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"

    @property
    def supabase_url(self) -> str | None:
        return self.keys.get("SUPABASE_URL")

    @property
    def supabase_service_key(self) -> str | None:
        return self.keys.get("SUPABASE_SERVICE_ROLE_KEY")

    @property
    def openai_api_key(self) -> str | None:
        return self.keys.get("OPENAI_API_KEY")

    @property
    def anthropic_api_key(self) -> str | None:
        return self.keys.get("ANTHROPIC_API_KEY")

    def pipeline_ready(self) -> bool:
        return all(self.keys.get(k) for k in PIPELINE_KEYS)


def _collect_keys() -> dict[str, str | None]:
    names = {k for group in REQUIRED_KEYS.values() for k in group}
    names.update(PIPELINE_KEYS)
    return {name: os.getenv(name) for name in sorted(names)}


def validate_environment() -> Settings:
    data_mode = os.getenv("GREENGAG_DATA_MODE", "mock").lower()
    if data_mode not in ("mock", "live"):
        raise RuntimeError(
            f"GREENGAG_DATA_MODE must be 'mock' or 'live', got '{data_mode}'."
        )

    keys = _collect_keys()
    missing = [k for k, v in keys.items() if not v and k in REQUIRED_KEYS]

    if data_mode == "live":
        pipeline_missing = [k for k in PIPELINE_KEYS if not keys.get(k)]
        if pipeline_missing:
            raise RuntimeError(
                "Missing pipeline keys for live document ingest/extract: "
                f"{', '.join(pipeline_missing)}"
            )
        other_missing = [
            k
            for group in REQUIRED_KEYS.values()
            for k in group
            if k not in PIPELINE_KEYS and not keys.get(k)
        ]
        if other_missing:
            logger.warning(
                "Live mode: optional agent keys not set (non-pipeline agents may fail): %s",
                ", ".join(other_missing),
            )
    elif missing:
        logger.warning(
            "Mock mode: %d secret(s) not set: %s",
            len(missing),
            ", ".join(missing),
        )

    return Settings(
        data_mode=data_mode,
        keys=keys,
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "2000")),
        rag_similarity_threshold=float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.55")),
        rag_top_k_per_pillar=int(os.getenv("RAG_TOP_K_PER_PILLAR", "8")),
        rag_max_chunks_to_llm=int(os.getenv("RAG_MAX_CHUNKS_TO_LLM", "20")),
        llm_extraction_model=os.getenv("LLM_EXTRACTION_MODEL", "claude-sonnet-4-5"),
    )


settings = validate_environment()
