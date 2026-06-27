"""Base agent contract.

Every agent is async (never blocking I/O), populates a rationale_trail for the
XAI display, and reports a risk_contribution in [0, 1] with a status drawn from
IDLE | PROCESSING | SUCCESS | ALERT (CLAUDE.md "Agent Implementation Notes").
"""

from __future__ import annotations

import abc
import asyncio

from config import settings
from models.schemas import BaseAgentState


class BaseAgent(abc.ABC):
    #: Key used in AgentStates and the Weighted Integrity Index.
    key: str = "BaseAgent"
    #: Human-facing name.
    name: str = "Base Agent"
    #: Simulated work duration in mock mode (seconds).
    mock_latency: float = 0.6

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or settings.data_mode

    async def run(self) -> BaseAgentState:
        """Execute the agent and return its populated state slice."""
        if self.mode == "live":
            return await self._run_live()
        await asyncio.sleep(self.mock_latency)
        return await self._run_mock()

    @abc.abstractmethod
    async def _run_mock(self) -> BaseAgentState:
        """Return deterministic fixture state."""

    async def _run_live(self) -> BaseAgentState:
        """Call real external APIs. Implemented per-agent in live mode."""
        raise NotImplementedError(
            f"{self.name} live mode is not wired yet. "
            "Run with GREENGAG_DATA_MODE=mock."
        )
