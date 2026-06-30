"""Environment & secrets binding with startup validation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Repo root `.env` (see README: cp .env.example .env from project root)
    _repo_root = Path(__file__).resolve().parent.parent
    load_dotenv(_repo_root / ".env")
    load_dotenv()  # optional backend/.env override
except ImportError:
    pass

logger = logging.getLogger("greengag.config")

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "Core orchestration": ("OPENAI_API_KEY",),
}

# Report Parser ingest + extract pipeline (RAG + OpenAI extraction).
PIPELINE_KEYS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENAI_API_KEY",
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
    rag_chunks_per_pillar: int
    rag_pillar_routing_model: str
    pillar_routing_confidence_floor: float
    llm_extraction_model: str
    openrouter_base_url: str
    openrouter_model: str

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
    def openrouter_api_key(self) -> str | None:
        return self.keys.get("OPENROUTER_API_KEY")

    @property
    def openrouter_online_model(self) -> str:
        model = self.openrouter_model.strip()
        if ":online" in model:
            return model
        return f"{model}:online"

    def live_benchmark_ready(self) -> bool:
        return bool(self.openrouter_api_key)

    def pipeline_ready(self) -> bool:
        return all(self.keys.get(k) for k in PIPELINE_KEYS)


def _collect_keys() -> dict[str, str | None]:
    names = {k for group in REQUIRED_KEYS.values() for k in group}
    names.update(PIPELINE_KEYS)
    names.add("OPENROUTER_API_KEY")
    return {name: os.getenv(name) for name in sorted(names)}


def validate_environment() -> Settings:
    data_mode = os.getenv("GREENGAG_DATA_MODE", "mock").lower()
    if data_mode not in ("mock", "live"):
        raise RuntimeError(
            f"GREENGAG_DATA_MODE must be 'mock' or 'live', got '{data_mode}'."
        )

    keys = _collect_keys()
    required_flat = {k for group in REQUIRED_KEYS.values() for k in group}
    missing = [k for k, v in keys.items() if not v and k in required_flat]

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
        rag_chunks_per_pillar=int(os.getenv("RAG_CHUNKS_PER_PILLAR", "3")),
        rag_pillar_routing_model=os.getenv(
            "RAG_PILLAR_ROUTING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        pillar_routing_confidence_floor=float(
            os.getenv("PILLAR_ROUTING_CONFIDENCE", "0.7")
        ),
        llm_extraction_model=os.getenv("LLM_EXTRACTION_MODEL", "gpt-4o"),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        openrouter_model=os.getenv(
            "OPENROUTER_MODEL", "google/gemini-2.5-flash"
        ),
    )


settings = validate_environment()
