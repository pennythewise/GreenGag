"""ERA5 weather ingestion subagent.

Pulls wind (u/v components) and total precipitation from ECMWF CDS
for the audit polygon. Credentials must be in ~/.cdsapirc.

Wind data feeds the NOAA HYSPLIT plume back-trajectory (step 4).
Precipitation data rules out drought as a confounding factor in NDVI audits.
"""

from __future__ import annotations

import asyncio

from models.schemas import GeoPolygon, LayerTimeSeries, SatelliteLayer, TimeSeriesPoint

from .result import IngestionResult

try:
    from agents.era5_ingestion import fetch_era5_precipitation, fetch_era5_wind
    _HAS_CDSAPI = True
except (ImportError, RuntimeError):
    _HAS_CDSAPI = False


class ERA5IngestionAgent:
    """Fetches ERA5 wind + precipitation for the audit polygon.

    Usage:
        result = await ERA5IngestionAgent(
            mock_wind_series=[("2025-Q1", 8, 9), ...],
            mock_precip_series=[("2024-Q1", 220, 215), ...],
        ).run(polygon)
    """

    def __init__(
        self,
        mode: str = "mock",
        mock_wind_series: list[tuple] | None = None,
        mock_precip_series: list[tuple] | None = None,
        include_precip: bool = False,
    ) -> None:
        self.mode = mode
        self._mock_wind = mock_wind_series or []
        self._mock_precip = mock_precip_series or []
        self.include_precip = include_precip  # True for reforestation audits

    async def run(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Return IngestionResult(s) for wind and optionally precipitation."""
        if self.mode == "live":
            return await self._run_live(polygon)
        await asyncio.sleep(0.25)
        return self._run_mock()

    def _run_mock(self) -> list[IngestionResult]:
        results = [
            IngestionResult(
                layer=SatelliteLayer(
                    layer_id="weather",
                    source="ECMWF_ERA5",
                    parameter="Wind Speed",
                    unit="m/s (10m surface)",
                    observed_variance_pct=0.0,
                    confidence_index=0.0,
                    anomaly_detected=False,
                    veto=False,
                ),
                series=LayerTimeSeries(
                    layer_id="weather",
                    label="Surface Wind Speed (ERA5)",
                    unit="m/s",
                    points=[
                        TimeSeriesPoint(date=d, claimed=c, observed=o)
                        for d, c, o in self._mock_wind
                    ],
                ),
                dataset=None,
            )
        ]
        if self.include_precip and self._mock_precip:
            results.append(
                IngestionResult(
                    layer=SatelliteLayer(
                        layer_id="precipitation",
                        source="ECMWF_ERA5",
                        parameter="Precipitation",
                        unit="mm/quarter",
                        observed_variance_pct=0.0,
                        confidence_index=0.0,
                        anomaly_detected=False,
                        veto=False,
                    ),
                    series=LayerTimeSeries(
                        layer_id="precipitation",
                        label="Precipitation (ERA5)",
                        unit="mm/quarter",
                        points=[
                            TimeSeriesPoint(date=d, claimed=c, observed=o)
                            for d, c, o in self._mock_precip
                        ],
                    ),
                    dataset=None,
                )
            )
        return results

    async def _run_live(self, polygon: GeoPolygon) -> list[IngestionResult]:
        """Download ERA5 wind + precipitation via CDS API.

        Steps:
        1. Call fetch_era5_wind(polygon) — downloads u10, v10 components as GRIB.
        2. Optionally call fetch_era5_precipitation(polygon) for reforestation audits.
        3. Both functions crop the raster to the polygon bounding box automatically.
        4. Return raw xarray Datasets for processing in steps 3-6.

        CDS request used (from ECMWF "Show API request"):
            dataset:  reanalysis-era5-single-levels
            variable: 10m_u_component_of_wind, 10m_v_component_of_wind
                      (+ total_precipitation if include_precip)
            area:     [N, W, S, E] derived from polygon bounding box
        """
        if not _HAS_CDSAPI:
            raise RuntimeError(
                "cdsapi not installed or ~/.cdsapirc not configured. "
                "Run: pip install cdsapi cfgrib xarray"
            )

        tasks = [fetch_era5_wind(polygon)]
        if self.include_precip:
            tasks.append(fetch_era5_precipitation(polygon))

        datasets = await asyncio.gather(*[asyncio.to_thread(t) for t in tasks])

        results = [
            IngestionResult(
                layer=SatelliteLayer(
                    layer_id="weather",
                    source="ECMWF_ERA5",
                    parameter="Wind Speed",
                    unit="m/s (10m surface)",
                    observed_variance_pct=0.0,
                    confidence_index=0.0,
                ),
                series=LayerTimeSeries(
                    layer_id="weather", label="Surface Wind Speed (ERA5)",
                    unit="m/s", points=[],
                ),
                dataset=datasets[0],
            )
        ]
        if self.include_precip and len(datasets) > 1:
            results.append(
                IngestionResult(
                    layer=SatelliteLayer(
                        layer_id="precipitation",
                        source="ECMWF_ERA5",
                        parameter="Precipitation",
                        unit="mm/quarter",
                        observed_variance_pct=0.0,
                        confidence_index=0.0,
                    ),
                    series=LayerTimeSeries(
                        layer_id="precipitation", label="Precipitation (ERA5)",
                        unit="mm/quarter", points=[],
                    ),
                    dataset=datasets[1],
                )
            )
        return results
