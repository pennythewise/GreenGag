"""Agent 4 — Media Sentinel (The Public Watchdog).

Scrapes news, community boards, and NGO databases, then runs NLP text
classification to flag contradictions between public reports and corporate
claims (e.g. "zero environmental incidents").
"""

from __future__ import annotations

from mocks import fixtures
from models.schemas import MediaSentinelState

from .base import BaseAgent


class MediaSentinelAgent(BaseAgent):
    key = "MediaSentinelAgent"
    name = "Media Sentinel Agent"
    mock_latency = 0.6

    async def _run_mock(self) -> MediaSentinelState:
        return fixtures.media_sentinel_state()

    async def _run_live(self) -> MediaSentinelState:
        # TODO(live): run scraping pipelines (NEWS_API_KEY + NGO sources) and a
        # contradiction classifier against the extracted claims.
        raise NotImplementedError(
            "MediaSentinelAgent live mode is not wired yet."
        )
