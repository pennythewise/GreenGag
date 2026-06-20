"""Sentinel-5P TROPOMI ingestion subagent.

Pulls NO₂, CH₄, and CO₂ tropospheric column data for the audit polygon
via the Sentinel Hub Process API.

Live mode requires: SENTINEL_HUB_CLIENT_ID, SENTINEL_HUB_CLIENT_SECRET
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from models.schemas import GeoPolygon, LayerTimeSeries, SatelliteLayer, TimeSeriesPoint

from .result import IngestionResult

try:
    import sentinelhub  # type: ignore
    _HAS_SENTINELHUB = True
except ImportError:
    _HAS_SENTINELHUB = False


# GHG parameters available via Sentinel-5P TROPOMI
GHG_LAYERS = {
    "no2": {
        "parameter": "NO2",
        "unit": "µmol/m² (tropospheric column)",
        "evalscript_band": "NO2",
    },
    "ch4": {
        "parameter": "CH4",
        "unit": "ppb (dry-air mole fraction)",
        "evalscript_band": "CH4",
    },
    "co2": {
        "parameter": "CO2",
        "unit": "ppm (column-averaged dry-air)",
        "evalscript_band": "CO2",
    },
}


class SentinelIngestionAgent:
    """Fetches one or more Sentinel-5P GHG layers for the audit polygon.

    Usage:
        result = await SentinelIngestionAgent(layer_ids=["no2", "ch4"]).run(polygon)
    """

    def __init__(
        self,
        layer_ids: list[str] | None = None,
        mode: str = "mock",
        mock_series: dict[str, list[tuple]] | None = None,
    ) -> None:
        self.layer_ids = layer_ids or ["no2"]
        self.mode = mode
        # mock_series: {"no2": [("2025-Q1", claimed, observed), ...], ...}
        self._mock_series = mock_series or {}

    async def run(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Return one IngestionResult per requested GHG layer."""
        if self.mode == "live":
            return await self._run_live(polygon)
        await asyncio.sleep(0.3)  # simulate network latency
        return self._run_mock()

    def _run_mock(self) -> list[IngestionResult]:
        results = []
        for lid in self.layer_ids:
            cfg = GHG_LAYERS[lid]
            pts = self._mock_series.get(lid, [])
            results.append(
                IngestionResult(
                    layer=SatelliteLayer(
                        layer_id=lid,
                        source="Sentinel-5P_TROPOMI",
                        parameter=cfg["parameter"],
                        unit=cfg["unit"],
                        observed_variance_pct=0.0,   # filled in by step 6
                        confidence_index=0.0,         # filled in by step 6
                        anomaly_detected=False,
                        veto=False,
                    ),
                    series=LayerTimeSeries(
                        layer_id=lid,
                        label=f"{cfg['parameter']} Tropospheric Column",
                        unit=cfg["unit"],
                        points=[
                            TimeSeriesPoint(date=d, claimed=c, observed=o)
                            for d, c, o in pts
                        ],
                    ),
                    dataset=None,
                )
            )
        return results

    async def _run_live(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Pull Sentinel-5P L2 NetCDF for each requested GHG layer.

        Steps:
        1. Build SentinelHub BBox from polygon coordinates.
        2. Construct an evalscript selecting the target band (NO2/CH4/CO2).
        3. Call SentinelHubRequest with DataCollection.SENTINEL5P.
        4. Receive NetCDF, open with xarray.
        5. Return IngestionResult with raw dataset (steps 3-6 process it later).
        """
        if not _HAS_SENTINELHUB:
            raise RuntimeError(
                "sentinelhub package not installed. "
                "Run: pip install sentinelhub"
            )
        # TODO(live): implement Sentinel Hub Process API call per layer
        # Reference: sentinelhub.SentinelHubRequest with DataCollection.SENTINEL5P
        raise NotImplementedError("Sentinel live ingestion not yet implemented.")
