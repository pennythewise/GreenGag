"""FastAPI application factory and entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from greengag.api.routes import audit, documents, health

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GreenGag Audit API",
    version="0.1.0",
    description="Multi-agent greenwashing detection backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
