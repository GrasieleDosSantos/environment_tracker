"""Geospatial helpers: point-in-polygon lookups, coordinate validation, region filtering.

Reads real boundary files from data/geojson/ (populated in Phase 0, task T000g).
GeoDataFrames are loaded once and cached in-process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape

from src.config.constants import BIOME_IDS, BRAZIL_BOUNDS, STATE_CODES
from src.utils.logging import get_logger

_log = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "geojson"

# Lazily loaded GeoDataFrames
_biomes_gdf: gpd.GeoDataFrame | None = None
_states_gdf: gpd.GeoDataFrame | None = None


def _load_biomes() -> gpd.GeoDataFrame:
    global _biomes_gdf
    if _biomes_gdf is None:
        path = _DATA_DIR / "biomes.geojson"
        _biomes_gdf = gpd.read_file(path).set_crs("EPSG:4326", allow_override=True)
        _log.info("biomes_loaded", count=len(_biomes_gdf))
    return _biomes_gdf


def _load_states() -> gpd.GeoDataFrame:
    global _states_gdf
    if _states_gdf is None:
        path = _DATA_DIR / "states.geojson"
        _states_gdf = gpd.read_file(path).set_crs("EPSG:4326", allow_override=True)
        _log.info("states_loaded", count=len(_states_gdf))
    return _states_gdf


# ------------------------------------------------------------------ #
# Coordinate validation                                                 #
# ------------------------------------------------------------------ #

def validate_brazilian_coordinates(lat: float, lon: float) -> bool:
    """Return True if (lat, lon) falls within Brazil's bounding box."""
    b = BRAZIL_BOUNDS
    return (
        b["min_lat"] <= lat <= b["max_lat"]
        and b["min_lon"] <= lon <= b["max_lon"]
    )


def transform_coordinates(
    lat: float, lon: float, from_crs: str = "EPSG:4674", to_crs: str = "EPSG:4326"
) -> tuple[float, float]:
    """Reproject a single coordinate pair between CRS.

    SIRGAS 2000 (EPSG:4674) and WGS 84 (EPSG:4326) differ by < 1 m for Brazil.
    For display-only use cases, the coordinates are effectively equivalent.
    """
    if from_crs == to_crs:
        return lat, lon

    gdf = gpd.GeoDataFrame(
        geometry=[Point(lon, lat)], crs=from_crs
    ).to_crs(to_crs)
    geom = gdf.geometry.iloc[0]
    return geom.y, geom.x  # lat, lon


# ------------------------------------------------------------------ #
# Point-in-polygon lookups                                              #
# ------------------------------------------------------------------ #

def get_point_biome(lat: float, lon: float) -> str | None:
    """Return the canonical biome ID for a coordinate, or None if outside all biomes."""
    if not validate_brazilian_coordinates(lat, lon):
        return None

    point = Point(lon, lat)
    gdf = _load_biomes()

    for _, row in gdf.iterrows():
        if row.geometry and row.geometry.contains(point):
            return str(row.get("id") or row.get("biome_id") or "")
    return None


def get_point_state(lat: float, lon: float) -> str | None:
    """Return the two-letter state code for a coordinate, or None if outside Brazil."""
    if not validate_brazilian_coordinates(lat, lon):
        return None

    point = Point(lon, lat)
    gdf = _load_states()

    for _, row in gdf.iterrows():
        if row.geometry and row.geometry.contains(point):
            return str(row.get("sigla") or row.get("code") or "")
    return None


# ------------------------------------------------------------------ #
# Region filtering                                                      #
# ------------------------------------------------------------------ #

def filter_by_region(
    records: list[dict[str, Any]],
    lat_key: str = "latitude",
    lon_key: str = "longitude",
    state: str | None = None,
    biome: str | None = None,
    region_type: str = "brazil",
) -> list[dict[str, Any]]:
    """Filter a list of dicts (or Pydantic-like objects) by geographic region.

    Filtering is done on pre-existing ``state``/``biome`` fields first;
    falls back to point-in-polygon lookup when those fields are absent.
    """
    if not records:
        return records

    result: list[dict[str, Any]] = []
    for rec in records:
        rec_dict = rec if isinstance(rec, dict) else rec.__dict__

        if state:
            rec_state = rec_dict.get("state") or rec_dict.get("uf")
            if rec_state:
                if rec_state.upper() != state.upper():
                    continue
            else:
                lat = rec_dict.get(lat_key)
                lon = rec_dict.get(lon_key)
                if lat is None or lon is None:
                    continue
                if get_point_state(float(lat), float(lon)) != state.upper():
                    continue

        if biome:
            rec_biome = rec_dict.get("biome") or rec_dict.get("bioma")
            if rec_biome:
                if rec_biome.lower() != biome.lower():
                    continue
            else:
                lat = rec_dict.get(lat_key)
                lon = rec_dict.get(lon_key)
                if lat is None or lon is None:
                    continue
                if get_point_biome(float(lat), float(lon)) != biome.lower():
                    continue

        result.append(rec_dict)

    return result


# ------------------------------------------------------------------ #
# GeoDataFrame helpers for map rendering                                #
# ------------------------------------------------------------------ #

def get_biomes_geodataframe() -> gpd.GeoDataFrame:
    """Return the biomes GeoDataFrame (WGS84)."""
    return _load_biomes().copy()


def get_states_geodataframe() -> gpd.GeoDataFrame:
    """Return the states GeoDataFrame (WGS84)."""
    return _load_states().copy()
