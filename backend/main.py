"""FastAPI entrypoint for the GreenGag audit backend.

Endpoints
---------
GET  /api/health         liveness + data-mode + secret presence (no values)
POST /api/audit          run the full multi-agent audit, return AuditPayload
GET  /api/audit/stream   Server-Sent Events: live agent transitions + verdict
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents import orchestrator
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("greengag")

app = FastAPI(
    title="GreenGag Audit API",
    version="0.1.0",
    description="Multi-agent greenwashing detection backend.",
)

# Dev frontend runs on Vite (5173). Tighten this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "data_mode": settings.data_mode,
        "langgraph": orchestrator._HAS_LANGGRAPH,
        # Report presence only — never echo secret values.
        "secrets_present": {k: bool(v) for k, v in settings.keys.items()},
    }


@app.post("/api/audit")
async def run_audit() -> dict:
    """Run the full audit graph once and return the assembled payload."""
    payload = await orchestrator.run_audit()
    return payload.model_dump()


@app.get("/api/audit/stream")
async def audit_stream() -> StreamingResponse:
    """Stream the audit as Server-Sent Events for live agent visualization."""

    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for event in orchestrator.stream_audit():
                yield f"data: {json.dumps(event)}\n\n".encode()
        except Exception as exc:  # surface failures to the client cleanly
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
