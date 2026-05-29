"""Multi-source data aggregator: merges DETER + FOGO into a unified environmental snapshot.

Responsibilities:
- Convert raw Pydantic model lists into analysis-ready pandas DataFrames
- Aggregate metrics across sources (area, count, risk)
- Resolve near-duplicate detections across satellites / sources
- Provide a single `create_unified_view()` entry point for the dashboard
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from src.config.constants import BIOMES, STATES
from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot
from src.services.inpe_integration.prodes_client import PRODESData
from src.utils.logging import get_logger

_log = get_logger(__name__)

# ------------------------------------------------------------------ #
# Domain snapshot                                                       #
# ------------------------------------------------------------------ #

@dataclass
class UnifiedSnapshot:
    """Aggregated environmental status for a region + time period."""

    region_label: str
    period_start: date
    period_end: date
    deforestation_km2: float
    deforestation_count: int
    fire_count_48h: int
    fire_count_period: int
    active_sources: list[str]
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    @property
    def fire_risk_level(self) -> str:
        if self.fire_count_48h > 1000:
            return "critical"
        if self.fire_count_48h > 500:
            return "high"
        if self.fire_count_48h > 100:
            return "medium"
        return "low"

    @property
    def fire_risk_label_pt(self) -> str:
        return {
            "critical": "Crítico / Critical",
            "high": "Alto / High",
            "medium": "Médio / Medium",
            "low": "Baixo / Low",
        }.get(self.fire_risk_level, "—")

    @property
    def fire_risk_colour(self) -> str:
        return {
            "critical": "#C0392B",
            "high": "#E67E22",
            "medium": "#F39C12",
            "low": "#27AE60",
        }.get(self.fire_risk_level, "#6C757D")


# ------------------------------------------------------------------ #
# DataFrame builders                                                    #
# ------------------------------------------------------------------ #

def deter_to_monthly_df(alerts: list[DETERAlert]) -> pd.DataFrame:
    """Monthly aggregation of deforestation area and alert count."""
    if not alerts:
        return pd.DataFrame(columns=["month", "area_km2", "count"])

    rows = [
        {
            "month": a.view_date.replace(day=1),
            "area_km2": a.area_km2 or 0.0,
            "state": a.state or "—",
            "biome": a.biome or "—",
            "classname": a.classname or "—",
        }
        for a in alerts
        if a.view_date
    ]
    if not rows:
        return pd.DataFrame(columns=["month", "area_km2", "count"])

    df = pd.DataFrame(rows)
    monthly = (
        df.groupby("month")
        .agg(area_km2=("area_km2", "sum"), count=("area_km2", "count"))
        .reset_index()
        .sort_values("month")
    )
    monthly["month"] = pd.to_datetime(monthly["month"])
    return monthly


def deter_to_state_df(alerts: list[DETERAlert]) -> pd.DataFrame:
    """Deforestation area and count grouped by state."""
    if not alerts:
        return pd.DataFrame(columns=["state", "area_km2", "count"])

    rows = [
        {"state": a.state or "—", "area_km2": a.area_km2 or 0.0}
        for a in alerts
    ]
    df = pd.DataFrame(rows)
    return (
        df.groupby("state")
        .agg(area_km2=("area_km2", "sum"), count=("area_km2", "count"))
        .reset_index()
        .sort_values("area_km2", ascending=False)
    )


def fogo_to_daily_df(hotspots: list[FireHotspot]) -> pd.DataFrame:
    """Daily fire hotspot counts."""
    if not hotspots:
        return pd.DataFrame(columns=["date", "count"])

    rows = []
    for h in hotspots:
        d = h.detection_time.date() if h.detection_time else h.date_pas
        if d:
            rows.append({"date": d})
    if not rows:
        return pd.DataFrame(columns=["date", "count"])

    df = pd.DataFrame(rows)
    daily = (
        df.groupby("date")
        .size()
        .reset_index(name="count")
        .sort_values("date")
    )
    daily["date"] = pd.to_datetime(daily["date"])
    return daily


def fogo_to_state_df(hotspots: list[FireHotspot]) -> pd.DataFrame:
    """Fire hotspot counts grouped by state."""
    if not hotspots:
        return pd.DataFrame(columns=["state", "count"])

    rows = [{"state": h.state or h.state_name or "—"} for h in hotspots]
    df = pd.DataFrame(rows)
    return (
        df.groupby("state")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def fogo_to_points_df(hotspots: list[FireHotspot]) -> pd.DataFrame:
    """Flat DataFrame of hotspot lat/lon points for map rendering."""
    if not hotspots:
        return pd.DataFrame(columns=["latitude", "longitude", "confidence", "frp", "state", "biome"])

    return pd.DataFrame(
        [
            {
                "latitude": h.latitude,
                "longitude": h.longitude,
                "confidence": h.confidence,
                "frp": h.frp,
                "state": h.state or "—",
                "biome": h.biome or "—",
                "satellite": h.satellite_source or "—",
            }
            for h in hotspots
            if h.latitude is not None and h.longitude is not None
        ]
    )


# ------------------------------------------------------------------ #
# Aggregation and conflict resolution                                   #
# ------------------------------------------------------------------ #

def aggregate_multi_source(
    deter_alerts: list[DETERAlert],
    fogo_hotspots_48h: list[FireHotspot],
    fogo_hotspots_period: list[FireHotspot],
    region_label: str,
    period_start: date,
    period_end: date,
) -> UnifiedSnapshot:
    """Merge DETER + FOGO data into a single UnifiedSnapshot."""
    deforestation_km2 = sum(a.area_km2 or 0.0 for a in deter_alerts)

    active: list[str] = []
    if deter_alerts:
        active.append("DETER")
    if fogo_hotspots_48h or fogo_hotspots_period:
        active.append("FOGO")

    _log.info(
        "snapshot_created",
        region=region_label,
        deforestation_km2=round(deforestation_km2, 2),
        fire_48h=len(fogo_hotspots_48h),
        fire_period=len(fogo_hotspots_period),
    )

    return UnifiedSnapshot(
        region_label=region_label,
        period_start=period_start,
        period_end=period_end,
        deforestation_km2=round(deforestation_km2, 2),
        deforestation_count=len(deter_alerts),
        fire_count_48h=len(fogo_hotspots_48h),
        fire_count_period=len(fogo_hotspots_period),
        active_sources=active,
    )


def resolve_conflicts(
    hotspots: list[FireHotspot],
    proximity_deg: float = 0.01,
) -> list[FireHotspot]:
    """Remove near-duplicate hotspot detections from different satellites.

    Two hotspots are considered duplicates when they share the same detection
    date and their coordinates are within *proximity_deg* degrees of each other.
    The record with the higher FRP value is kept.
    """
    if len(hotspots) <= 1:
        return hotspots

    kept: list[FireHotspot] = []
    for h in sorted(hotspots, key=lambda x: x.frp or 0.0, reverse=True):
        if h.latitude is None or h.longitude is None:
            kept.append(h)
            continue

        h_date = h.detection_time.date() if h.detection_time else None
        duplicate = False
        for k in kept:
            if k.latitude is None or k.longitude is None:
                continue
            k_date = k.detection_time.date() if k.detection_time else None
            if (
                h_date == k_date
                and abs(h.latitude - k.latitude) < proximity_deg
                and abs(h.longitude - k.longitude) < proximity_deg
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(h)

    _log.debug("resolve_conflicts", before=len(hotspots), after=len(kept))
    return kept


def create_unified_view(
    states: list[str] | None = None,
    biomes: list[str] | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> UnifiedSnapshot:
    """Fetch from DETER + FOGO and return an aggregated UnifiedSnapshot.

    Accepts multi-state / multi-biome filters; fetches without server-side
    filter when multiple values are selected and applies client-side filtering.
    """
    from src.services.inpe_integration.deter_client import fetch_deter_time_series
    from src.services.inpe_integration.fogo_client import (
        fetch_current_hotspots,
        fetch_fire_risk,
    )
    from src.utils.date_utils import today_brazil

    if period_end is None:
        period_end = today_brazil()
    if period_start is None:
        from datetime import timedelta
        period_start = period_end - timedelta(days=30)

    # Single-value filters map directly to WFS parameters;
    # multi-value fetch unfiltered and filter client-side.
    single_state = states[0] if states and len(states) == 1 else None
    single_biome = biomes[0] if biomes and len(biomes) == 1 else None

    region_parts: list[str] = []
    if biomes:
        biome_names = [
            next((b["name"] for b in BIOMES if b["id"] == bid), bid)
            for bid in biomes
        ]
        region_parts.extend(biome_names)
    if states:
        region_parts.extend(
            STATES.get(s, s) for s in states
        )
    region_label = ", ".join(region_parts) if region_parts else "Brasil"

    try:
        deter_alerts = fetch_deter_time_series(
            state=single_state,
            biome=single_biome,
            start=period_start,
            end=period_end,
        )
    except Exception as exc:
        _log.error("deter_fetch_failed", error=str(exc))
        deter_alerts = []

    try:
        fogo_48h = fetch_current_hotspots(
            state=single_state,
            biome=single_biome,
        )
    except Exception as exc:
        _log.error("fogo_48h_fetch_failed", error=str(exc))
        fogo_48h = []

    try:
        fogo_period = fetch_fire_risk(
            state=single_state,
            biome=single_biome,
            days=(period_end - period_start).days,
        )
    except Exception as exc:
        _log.error("fogo_period_fetch_failed", error=str(exc))
        fogo_period = []

    # Client-side filter when multiple states/biomes selected
    if states and len(states) > 1:
        deter_alerts = [a for a in deter_alerts if a.state in states]
        fogo_48h = [h for h in fogo_48h if h.state in states]
        fogo_period = [h for h in fogo_period if h.state in states]

    if biomes and len(biomes) > 1:
        biome_names_lower = {
            b["name"].lower() for bid in biomes
            for b in BIOMES if b["id"] == bid
        }
        deter_alerts = [
            a for a in deter_alerts
            if (a.biome or "").lower() in biome_names_lower
        ]
        fogo_48h = [
            h for h in fogo_48h
            if (h.biome or "").lower() in biome_names_lower
        ]
        fogo_period = [
            h for h in fogo_period
            if (h.biome or "").lower() in biome_names_lower
        ]

    return aggregate_multi_source(
        deter_alerts=deter_alerts,
        fogo_hotspots_48h=fogo_48h,
        fogo_hotspots_period=fogo_period,
        region_label=region_label,
        period_start=period_start,
        period_end=period_end,
    )
