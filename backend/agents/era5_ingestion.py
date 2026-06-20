"""ERA5 wind + precipitation ingestion via ECMWF CDS API.

Credentials must be set up in ~/.cdsapirc (url + key).
No environment variable needed — cdsapi reads the file automatically.

Usage:
    from agents.era5_ingestion import fetch_era5_wind, fetch_era5_precipitation
"""

from __future__ import annotations

import tempfile
from pathlib import Path

try:
    import cdsapi
    import xarray as xr
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

from models.schemas import GeoPolygon


def _polygon_to_area(polygon: GeoPolygon) -> list[float]:
    """Convert a GeoJSON Polygon to CDS area bounding box [N, W, S, E]."""
    coords = [pt for ring in polygon.coordinates for pt in ring]
    lngs = [pt[0] for pt in coords]
    lats = [pt[1] for pt in coords]
    # CDS expects [North, West, South, East] with a small buffer
    buffer = 0.1
    return [
        round(max(lats) + buffer, 4),
        round(min(lngs) - buffer, 4),
        round(min(lats) - buffer, 4),
        round(max(lngs) + buffer, 4),
    ]


def _year_month_range(start_year: int, end_year: int) -> tuple[list[str], list[str]]:
    years = [str(y) for y in range(start_year, end_year + 1)]
    months = [f"{m:02d}" for m in range(1, 13)]
    return years, months


def fetch_era5_wind(
    polygon: GeoPolygon,
    start_year: int = 2024,
    end_year: int = 2026,
) -> "xr.Dataset":
    """Download ERA5 10m wind components (u + v) for the audit polygon.

    Returns an xarray Dataset with variables:
        u10  — eastward wind component (m/s)
        v10  — northward wind component (m/s)
    Monthly means, cropped to the polygon bounding box.

    The u/v components feed into NOAA HYSPLIT for plume back-trajectory.
    Wind speed  = sqrt(u10² + v10²)
    Wind direction = atan2(u10, v10)
    """
    years, months = _year_month_range(start_year, end_year)
    area = _polygon_to_area(polygon)

    request = {
        "product_type": ["reanalysis"],
        "variable": [
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
        ],
        "year": years,
        "month": months,
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,           # crop to polygon bounding box
        "data_format": "grib",
        "download_format": "unarchived",
    }

    return _retrieve_and_load("reanalysis-era5-single-levels", request)


def fetch_era5_precipitation(
    polygon: GeoPolygon,
    start_year: int = 2024,
    end_year: int = 2026,
) -> "xr.Dataset":
    """Download ERA5 total precipitation for the audit polygon.

    Returns an xarray Dataset with variable:
        tp  — total precipitation (m, convert to mm by * 1000)
    Monthly means, cropped to the polygon bounding box.

    Used in reforestation audits to rule out drought as a confounding
    factor when NDVI shows low canopy recovery.
    """
    years, months = _year_month_range(start_year, end_year)
    area = _polygon_to_area(polygon)

    request = {
        "product_type": ["reanalysis"],
        "variable": ["total_precipitation"],
        "year": years,
        "month": months,
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "data_format": "grib",
        "download_format": "unarchived",
    }

    return _retrieve_and_load("reanalysis-era5-single-levels", request)


def _retrieve_and_load(dataset: str, request: dict) -> "xr.Dataset":
    """Download via CDS API into a temp file, open with xarray, return Dataset."""
    if not _DEPS_AVAILABLE:
        raise RuntimeError(
            "ERA5 ingestion requires cdsapi and xarray. "
            "Run: pip install cdsapi cfgrib xarray rioxarray"
        )
    client = cdsapi.Client()
    with tempfile.NamedTemporaryFile(suffix=".grib", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    client.retrieve(dataset, request).download(tmp_path)
    ds = xr.open_dataset(tmp_path, engine="cfgrib")
    return ds
