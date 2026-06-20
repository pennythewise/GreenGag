"""Planet Labs NDVI ingestion subagent.

Pulls PSSScene 4-band multispectral imagery for the audit polygon via
the Planet Labs Data API, then computes NDVI per pixel.

Used only for reforestation audits — triggered when the project type
indicates canopy coverage verification is needed.

Live mode requires: PLANET_LABS_API_KEY
"""

from __future__ import annotations

import asyncio
import os

from models.schemas import GeoPolygon, LayerTimeSeries, SatelliteLayer, TimeSeriesPoint

from .result import IngestionResult

try:
    import planet  # type: ignore
    _HAS_PLANET = True
except ImportError:
    _HAS_PLANET = False


class NDVIIngestionAgent:
    """Fetches Planet Labs NDVI for the audit polygon.

    NDVI = (NIR - Red) / (NIR + Red)
    Canopy threshold: NDVI > 0.35 = active vegetation cover.

    Usage:
        result = await NDVIIngestionAgent(
            mock_ndvi_series=[("2024-Q1", 0.12, 0.11), ...],
        ).run(polygon)
    """

    def __init__(
        self,
        mode: str = "mock",
        mock_ndvi_series: list[tuple] | None = None,
    ) -> None:
        self.mode = mode
        self._mock_ndvi = mock_ndvi_series or []

    async def run(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Return one IngestionResult for the NDVI layer."""
        if self.mode == "live":
            return await self._run_live(polygon)
        await asyncio.sleep(0.35)  # simulate imagery download latency
        return self._run_mock()

    def _run_mock(self) -> list[IngestionResult]:
        return [
            IngestionResult(
                layer=SatelliteLayer(
                    layer_id="ndvi",
                    source="Planet_NDVI",
                    parameter="NDVI",
                    unit="index (0–1, canopy threshold > 0.35)",
                    observed_variance_pct=0.0,
                    confidence_index=0.0,
                    anomaly_detected=False,
                    veto=False,
                ),
                series=LayerTimeSeries(
                    layer_id="ndvi",
                    label="NDVI Canopy Coverage (area-mean)",
                    unit="index (0–1)",
                    points=[
                        TimeSeriesPoint(date=d, claimed=c, observed=o)
                        for d, c, o in self._mock_ndvi
                    ],
                ),
                dataset=None,
            )
        ]

    async def _run_live(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Download Planet Labs PSSScene imagery and compute NDVI.

        Steps:
        1. Authenticate with Planet Data API using PLANET_LABS_API_KEY.
        2. Search for PSScene assets over the polygon + date range
           (item_type="PSScene", asset_type="ortho_analytic_4b_sr").
        3. Activate and download the 4-band GeoTIFF (B, G, R, NIR).
        4. Compute NDVI = (NIR - R) / (NIR + R) per pixel using rioxarray.
        5. Clip to the polygon boundary.
        6. Compute area-mean NDVI per quarter → time series.
        7. Return raw dataset for step 6 (anomaly z-scoring against baseline).
        """
        if not _HAS_PLANET:
            raise RuntimeError(
                "planet package not installed. Run: pip install planet"
            )
        api_key = os.getenv("PLANET_LABS_API_KEY")
        if not api_key:
            raise RuntimeError("PLANET_LABS_API_KEY not set in environment.")

        # TODO(live): implement Planet Data API search + download
        # async with planet.Session(auth=planet.Auth.from_key(api_key)) as session:
        #     client = session.client("data")
        #     search = await client.quick_search(...)
        raise NotImplementedError("Planet Labs live ingestion not yet implemented.")
