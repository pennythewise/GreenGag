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
        "secrets_present": {k: bool(v) for k, v in settings.keys.items()},
    }
