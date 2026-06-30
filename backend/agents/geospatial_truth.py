"""Agent 5 — Geospatial Truth (The Ultimate Juror).

Queries remote-sensing satellite APIs over the target polygon and measures the
physical state of the atmosphere/terrain across a time series. Holds absolute
veto power over the final verdict (CLAUDE.md "Weighted Integrity Index").
"""

from __future__ import annotations

from mocks import fixtures
from models.schemas import GeospatialTruthState

from .base import BaseAgent


class GeospatialTruthAgent(BaseAgent):
    key = "GeospatialTruthAgent"
    name = "Geospatial Truth Agent"
    mock_latency = 0.9

    async def _run_mock(self) -> GeospatialTruthState:
        return fixtures.geospatial_truth_state()

    async def _run_live(self) -> GeospatialTruthState:
        # TODO(live): wire a remote-sensing provider over the target polygon,
        # compute the NO2 running mean, and assert veto on a flatline.
        raise NotImplementedError(
            "GeospatialTruthAgent live mode is not wired yet."
        )

    def asserts_veto(self, state: GeospatialTruthState) -> bool:
        """True when physical evidence contradicts the corporate claim."""
        return bool(state.metrics and state.metrics.veto)
