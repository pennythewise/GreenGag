"""Environment & secrets binding with startup validation.

All secrets are read via os.getenv() — never hardcoded (CLAUDE.md / PRD §3.3).
The boot validator verifies required keys at startup:

- live mode  -> any missing key raises a RuntimeError with an explicit message.
- mock mode  -> missing keys are reported as warnings so the demo runs offline.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; real env vars still work.
    pass

logger = logging.getLogger("greengag.config")

# Keys required for full (live) operation, grouped for readable error output.
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


@dataclass(frozen=True)
class Settings:
    data_mode: str  # "mock" | "live"
    keys: dict[str, str | None]

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"


def _collect_keys() -> dict[str, str | None]:
    keys: dict[str, str | None] = {}
    for group in REQUIRED_KEYS.values():
        for key in group:
            keys[key] = os.getenv(key)
    return keys


def validate_environment() -> Settings:
    """Validate required env vars; behavior depends on GREENGAG_DATA_MODE."""
    data_mode = os.getenv("GREENGAG_DATA_MODE", "mock").lower()
    if data_mode not in ("mock", "live"):
        raise RuntimeError(
            f"GREENGAG_DATA_MODE must be 'mock' or 'live', got '{data_mode}'."
        )

    keys = _collect_keys()
    missing = [k for k, v in keys.items() if not v]

    if missing:
        detail = ", ".join(missing)
        if data_mode == "live":
            raise RuntimeError(
                "Missing required environment variables for live mode: "
                f"{detail}. Copy .env.example to .env and fill them in."
            )
        logger.warning(
            "Running in MOCK mode. %d secret(s) not set (fine for the demo): %s",
            len(missing),
            detail,
        )
    else:
        logger.info("All %d required secrets present.", len(keys))

    return Settings(data_mode=data_mode, keys=keys)


settings = validate_environment()
