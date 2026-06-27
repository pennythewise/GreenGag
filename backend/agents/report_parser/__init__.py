"""Report Parser Agent — PDF ingest, RAG extraction, and claim normalization."""

from __future__ import annotations

from mocks import fixtures
from models.schemas import ReportParserState

from ..base import BaseAgent
from .extract import ExtractPipeline
from .ingest import IngestPipeline
from .report.renderer import render_extraction_report_pdf


class ReportParserAgent(BaseAgent):
    """Agent 2 — Report Parser (The Reader).

    Ingests corporate ESG PDFs and extracts measurable claims into structured JSON
    for downstream agents.
    """

    key = "ReportParserAgent"
    name = "Report Parser Agent"
    mock_latency = 0.5

    async def _run_mock(self) -> ReportParserState:
        return fixtures.report_parser_state()

    async def _run_live(self) -> ReportParserState:
        # TODO(live): wire IngestPipeline + ExtractPipeline for orchestrator SSE.
        raise NotImplementedError(
            "ReportParserAgent live mode requires a PDF source + OPENAI_API_KEY."
        )


__all__ = [
    "ReportParserAgent",
    "IngestPipeline",
    "ExtractPipeline",
    "render_extraction_report_pdf",
]
