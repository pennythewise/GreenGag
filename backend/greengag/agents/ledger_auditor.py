"""Agent 3 — Ledger Auditor (The Accountant).

Runs deterministic tabular calculations over procurement ledgers, invoices, and
BOMs to compare verified eco-material spend against high-carbon suppliers and
detect bait-and-switch financial fraud.
"""

from __future__ import annotations

from greengag.mocks import fixtures
from greengag.models.schemas import LedgerAuditorState

from .base import BaseAgent


class LedgerAuditorAgent(BaseAgent):
    key = "LedgerAuditorAgent"
    name = "Ledger Auditor Agent"
    mock_latency = 0.7

    async def _run_mock(self) -> LedgerAuditorState:
        return fixtures.ledger_auditor_state()

    async def _run_live(self) -> LedgerAuditorState:
        # TODO(live): async query INTERNAL_LEDGER_DB_URL, join against the
        # approved-green-vendor index, and compute the spend split.
        raise NotImplementedError(
            "LedgerAuditorAgent live mode requires INTERNAL_LEDGER_DB_URL."
        )
