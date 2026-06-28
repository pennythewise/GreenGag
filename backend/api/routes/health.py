"""Health and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter

from agents import orchestrator
from config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "data_mode": settings.data_mode,
        "langgraph": orchestrator._HAS_LANGGRAPH,
        "live_benchmark": {
            "provider": "openrouter",
            "model": settings.openrouter_online_model,
            "ready": settings.live_benchmark_ready(),
        },
        "secrets_present": {k: bool(v) for k, v in settings.keys.items()},
    }
