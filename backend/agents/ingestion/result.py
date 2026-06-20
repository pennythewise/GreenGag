"""Shared result type returned by every ingestion subagent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.schemas import LayerTimeSeries, SatelliteLayer


@dataclass
class IngestionResult:
    """What each ingestion subagent hands back to GeospatialTruthAgent.

    In mock mode:  `dataset` is None; `layer` and `series` carry fixture data.
    In live mode:  `dataset` holds the raw xarray Dataset; `layer` and `series`
                   are populated after processing (steps 3-6).
    """
    layer: SatelliteLayer
    series: LayerTimeSeries
    dataset: Any = field(default=None, repr=False)  # xr.Dataset | None
