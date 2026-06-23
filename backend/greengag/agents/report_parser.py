"""Agent 2 — Report Parser (The Reader).

Ingests corporate ESG PDFs, strips promotional fluff, and extracts concrete,
measurable claims (carbon targets, materials, budgets, geo bounding boxes) into
structured JSON for the downstream agents.
"""

from __future__ import annotations

from greengag.mocks import fixtures
from greengag.models.schemas import ReportParserState

from .base import BaseAgent


class ReportParserAgent(BaseAgent):
    key = "ReportParserAgent"
    name = "Report Parser Agent"
    mock_latency = 0.5

    async def _run_mock(self) -> ReportParserState:
        return fixtures.report_parser_state()

    async def _run_live(self) -> ReportParserState:
        # TODO(live): pull the source PDF, run layout extraction, then call
        # OpenAI to normalize claims into JSON.
        raise NotImplementedError(
            "ReportParserAgent live mode requires a PDF source + OPENAI_API_KEY."
        )
