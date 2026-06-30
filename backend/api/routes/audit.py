"""Audit run + SSE stream endpoints."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agents import orchestrator

logger = logging.getLogger("greengag.api.audit")
router = APIRouter(tags=["audit"])


@router.post("/audit")
async def run_audit() -> dict:
    payload = await orchestrator.run_audit()
    return payload.model_dump()


@router.get("/audit/stream")
async def audit_stream() -> StreamingResponse:
    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for event in orchestrator.stream_audit():
                yield f"data: {json.dumps(event)}\n\n".encode()
        except Exception as exc:
            logger.exception("audit stream failed")
            err = {"type": "error", "message": str(exc), "payload": None}
            yield f"data: {json.dumps(err)}\n\n".encode()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
