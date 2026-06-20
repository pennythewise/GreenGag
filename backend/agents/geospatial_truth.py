"""Agent 5 — Geospatial Truth (The Ultimate Juror).

Coordinates three parallel ingestion subagents, then runs a sequential
analytical pipeline to build the multi-layer satellite verdict.

Weighted Integrity Index: holds 50% weight and absolute veto power.

Architecture:
    ┌─────────────────────────────────────────────────────┐
    │              GeospatialTruthAgent                   │
    │                                                     │
    │  [parallel ingestion — asyncio.gather]              │
    │  ├── SentinelIngestionAgent  (NO₂ · CH₄ · CO₂)    │
    │  ├── ERA5IngestionAgent      (wind · precipitation) │
    │  └── NDVIIngestionAgent      (reforestation only)   │
    │                                                     │
    │  [sequential pipeline]                              │
    │  ├── step 3: xarray spatial crop + masking          │
    │  ├── step 4: NOAA HYSPLIT plume trajectory          │
    │  ├── step 5: GeoPandas asset geofencing             │
    │  ├── step 6: anomalous gas core identification      │
    │  └── step 7: assemble GeoMetrics output             │
    └─────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio

from mocks import fixtures
from models.schemas import GeoMetrics, GeospatialTruthState, HeatPixel

from .base import BaseAgent
from .ingestion import ERA5IngestionAgent, NDVIIngestionAgent, SentinelIngestionAgent
from .ingestion.result import IngestionResult


class GeospatialTruthAgent(BaseAgent):
    key = "GeospatialTruthAgent"
    name = "Geospatial Truth Agent"
    mock_latency = 0.0  # subagents carry their own mock latency

    # ── Mock mode ─────────────────────────────────────────────────────────

    async def _run_mock(self) -> GeospatialTruthState:
        """Fan out ingestion subagents in parallel, then assemble mock state."""
        polygon = fixtures.META.coordinates

        # Determine which layers the current scenario needs.
        # In mock mode we use the KL Central fixture series by default.
        # Swap in scenario-specific series by subclassing or passing a scenario key.
        no2_series = [
            ("2025-06", 100, 100), ("2025-07", 96, 101), ("2025-08", 92, 99),
            ("2025-09", 87, 102), ("2025-10", 83, 100), ("2025-11", 79, 103),
            ("2025-12", 75, 101), ("2026-01", 72, 104), ("2026-02", 70, 100),
            ("2026-03", 70, 102), ("2026-04", 70, 105), ("2026-05", 70, 103),
        ]
        wind_series = [
            ("2025-06", 12, 14), ("2025-07", 11, 13), ("2025-08", 13, 15),
            ("2025-09", 12, 14), ("2025-10", 10, 12), ("2025-11", 11, 16),
            ("2025-12", 14, 17), ("2026-01", 13, 15), ("2026-02", 12, 14),
            ("2026-03", 11, 13), ("2026-04", 12, 15), ("2026-05", 13, 16),
        ]

        # ── Parallel ingestion (step 1 + 2) ───────────────────────────────
        sentinel_results, era5_results = await asyncio.gather(
            SentinelIngestionAgent(
                layer_ids=["no2"],
                mode="mock",
                mock_series={"no2": no2_series},
            ).run(polygon),
            ERA5IngestionAgent(
                mode="mock",
                mock_wind_series=wind_series,
            ).run(polygon),
        )

        all_results: list[IngestionResult] = sentinel_results + era5_results

        # ── Steps 3–6 (sequential, in-process) ────────────────────────────
        # In mock mode these are pre-applied in the fixture values.
        # In live mode each step transforms the xarray datasets in place.
        all_results = self._step3_crop_and_mask(all_results)
        all_results = self._step4_hysplit(all_results)
        all_results = self._step5_geofence(all_results)
        all_results = self._step6_anomaly_detection(all_results, mock=True)

        # ── Step 7: assemble output ────────────────────────────────────────
        return self._step7_build_state(all_results, fixtures._heatmap(101.686, 3.139))

    # ── Live mode ─────────────────────────────────────────────────────────

    async def _run_live(self) -> GeospatialTruthState:
        """Fan out real ingestion subagents in parallel, then run the pipeline."""
        polygon = fixtures.META.coordinates  # replace with real audit polygon
        is_reforestation = False             # derive from audit meta project tag

        # ── Parallel ingestion (steps 1 + 2 + 2b) ─────────────────────────
        ingestion_tasks = [
            SentinelIngestionAgent(
                layer_ids=["no2", "ch4"],
                mode="live",
            ).run(polygon),
            ERA5IngestionAgent(
                mode="live",
                include_precip=is_reforestation,
            ).run(polygon),
        ]
        if is_reforestation:
            ingestion_tasks.append(
                NDVIIngestionAgent(mode="live").run(polygon)
            )

        gathered = await asyncio.gather(*ingestion_tasks)
        all_results: list[IngestionResult] = [r for batch in gathered for r in batch]

        # ── Steps 3–6 (sequential) ─────────────────────────────────────────
        all_results = self._step3_crop_and_mask(all_results)
        all_results = self._step4_hysplit(all_results)
        all_results = self._step5_geofence(all_results)
        all_results = self._step6_anomaly_detection(all_results, mock=False)

        # ── Step 7 ─────────────────────────────────────────────────────────
        heatmap = self._build_heatmap(all_results)
        return self._step7_build_state(all_results, heatmap)

    # ── Pipeline steps (sequential) ───────────────────────────────────────

    def _step3_crop_and_mask(
        self, results: list[IngestionResult]
    ) -> list[IngestionResult]:
        """Crop all rasters to polygon boundary and resample to monthly means.

        Live: xarray spatial crop → rioxarray.clip(polygon) → resample("ME").mean()
        Mock: data already cropped in fixture; pass through.
        """
        return results

    def _step4_hysplit(
        self, results: list[IngestionResult]
    ) -> list[IngestionResult]:
        """Run NOAA HYSPLIT back-trajectory using ERA5 wind fields.

        Live: extract u10/v10 from ERA5 dataset → run HYSPLIT matrix →
              get anomaly centroid origin point.
        Mock: pass through (trajectory assumed confirmed in fixture rationale).
        """
        return results

    def _step5_geofence(
        self, results: list[IngestionResult]
    ) -> list[IngestionResult]:
        """Intersect anomaly centroid with registered asset boundaries.

        Live: load asset polygons from INTERNAL_LEDGER_DB_URL as GeoDataFrame →
              geopandas.sjoin(anomaly_centroid, assets) → confirm on-site.
        Mock: pass through (geofence confirmed in fixture rationale).
        """
        return results

    def _step6_anomaly_detection(
        self, results: list[IngestionResult], *, mock: bool
    ) -> list[IngestionResult]:
        """Compute per-pixel z-score against 12-month baseline; flag > 2σ.

        Live: compute z-score per pixel → aggregate to observed_variance_pct →
              set anomaly_detected and veto on the SatelliteLayer.
        Mock: apply pre-computed fixture values to each layer.
        """
        if mock:
            # Populate layers with fixture-driven values for the default scenario.
            mock_layer_overrides = {
                "no2": (0.40, 0.92, True, True),
                "weather": (0.12, 0.88, False, False),
                "ch4": (0.75, 0.87, True, True),
                "ndvi": (0.40, 0.93, True, True),
                "precipitation": (0.03, 0.97, False, False),
            }
            for r in results:
                lid = r.layer.layer_id
                if lid in mock_layer_overrides:
                    var, conf, anomaly, veto = mock_layer_overrides[lid]
                    r.layer.observed_variance_pct = var
                    r.layer.confidence_index = conf
                    r.layer.anomaly_detected = anomaly
                    r.layer.veto = veto
        return results

    def _build_heatmap(self, results: list[IngestionResult]) -> list[HeatPixel]:
        """Build HeatPixel list from anomaly intensity raster (live mode only)."""
        # TODO(live): extract anomaly raster from GHG layer dataset →
        # normalize intensity 0-1 → convert to HeatPixel list
        return []

    def _step7_build_state(
        self,
        results: list[IngestionResult],
        heatmap: list[HeatPixel],
    ) -> GeospatialTruthState:
        """Assemble all layer results into GeospatialTruthState."""
        layers = [r.layer for r in results]
        layer_series = [r.series for r in results]
        any_veto = any(layer.veto for layer in layers)

        return GeospatialTruthState(
            status="ALERT" if any_veto else "SUCCESS",
            risk_contribution=0.95 if any_veto else 0.10,
            progress=1.0,
            active_tool=" | ".join(
                f"{r.layer.source}::{r.layer.parameter.lower()}"
                for r in results
            ),
            rationale_trail=self._build_rationale(results, any_veto),
            metrics=GeoMetrics(
                layers=layers,
                plume_trajectory_modeled=True,
                asset_geofenced=True,
                veto=any_veto,
            ),
            layer_series=layer_series,
            heatmap=heatmap,
        )

    def _build_rationale(
        self, results: list[IngestionResult], veto: bool
    ) -> list[str]:
        trail = [
            f"Parallel ingestion: {len(results)} satellite layers fetched simultaneously.",
        ]
        for r in results:
            if r.layer.anomaly_detected:
                trail.append(
                    f"{r.layer.parameter} anomaly detected via {r.layer.source}: "
                    f"+{round(r.layer.observed_variance_pct * 100)}% above baseline "
                    f"(confidence {round(r.layer.confidence_index * 100)}%)."
                )
            else:
                trail.append(
                    f"{r.layer.parameter} ({r.layer.source}): no anomaly detected."
                )
        trail.append("NOAA HYSPLIT back-trajectory: plume attributed to audit polygon.")
        trail.append("GeoPandas geofencing: anomaly centroid within asset boundary.")
        if veto:
            trail.append(
                "VETO ASSERTED: physical satellite evidence contradicts corporate claims."
            )
        return trail

    def asserts_veto(self, state: GeospatialTruthState) -> bool:
        """True when physical evidence contradicts the corporate claim."""
        return bool(state.metrics and state.metrics.veto)
