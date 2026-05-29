"""DETER — near-real-time deforestation alert client.

WFS endpoint: terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows
Layer:        deter-amz:deter_amz
Update freq:  daily (16-day satellite revisit)
Cache TTL:    24 h
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.config.constants import BIOMES
from src.config.settings import get_settings
from src.services.inpe_integration.base import BaseINPEClient
from src.services.inpe_integration.cache_manager import get_cache_manager
from src.utils.decorators import async_safe

# Biomes that have a dedicated near-real-time DETER layer on TerraBrasilis.
# All other biomes fall back to PRODES annual data only.
_DETER_BIOME_LAYERS: dict[str, str] = {
    "amazonia": "deter-amz:deter_amz",
    "cerrado":  "deter-cerrado:deter_cerrado",
}

# Canonical display names keyed by biome ID (used to inject biome field into records)
_BIOME_DISPLAY: dict[str, str] = {b["id"]: b["name"] for b in BIOMES}


class DETERAlert(BaseModel):
    """One DETER alert feature (GeoJSON Feature → flat model)."""

    view_date: date | None = None
    classname: str | None = None
    state: str | None = None
    area_km2: float | None = None
    municipality: str | None = None
    biome: str | None = None
    geometry_type: str | None = None
    geometry_coordinates: Any = None

    @model_validator(mode="before")
    @classmethod
    def _from_feature(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        # Direct field construction (no GeoJSON wrapper) — pass through unchanged
        if "properties" not in v and "geometry" not in v:
            return v
        props = v.get("properties") or {}
        geom = v.get("geometry") or {}

        def _first(*keys: str) -> Any:
            for k in keys:
                if (val := props.get(k)) is not None:
                    return val
            return None

        raw_date = _first("VIEW_DATE", "view_date")
        parsed_date: date | None = None
        if isinstance(raw_date, str):
            try:
                parsed_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                pass
        elif isinstance(raw_date, (date, datetime)):
            parsed_date = raw_date if isinstance(raw_date, date) else raw_date.date()

        return {
            "view_date": parsed_date,
            "classname": _first("CLASSNAME", "classname"),
            "state": _first("UF", "uf", "state"),
            "area_km2": _first("AREAMUNKM", "areamunkm", "AREAKM2", "area_km2"),
            "municipality": _first("MUNICIPIO", "municipio", "municipality"),
            "biome": _first("BIOMA", "bioma", "biome"),
            "geometry_type": geom.get("type"),
            "geometry_coordinates": geom.get("coordinates"),
        }


class DETERClient(BaseINPEClient):
    source_name = "DETER"
    layer_name = "deter-amz:deter_amz"
    default_cache_ttl = 86400  # 24 h

    def __init__(self, endpoint: str | None = None, layer: str | None = None) -> None:
        settings = get_settings()
        self.wfs_endpoint = endpoint or settings.inpe_deter_endpoint
        if layer:
            self.layer_name = layer
        super().__init__(rate_limit=settings.rate_limit_deter)
        self._cache = get_cache_manager()

    # ------------------------------------------------------------------ #
    # Public async API                                                      #
    # ------------------------------------------------------------------ #

    async def fetch_alerts_by_region(
        self,
        state: str | None = None,
        biome: str | None = None,
        classname: str | None = None,
        since: date | None = None,
        count: int = 500,
    ) -> list[DETERAlert]:
        """Fetch recent DETER alerts, optionally filtered by region/type/date."""
        params: dict[str, Any] = {
            "state": state,
            "biome": biome,
            "classname": classname,
            "since": since,
            "count": count,
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [DETERAlert.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if since:
            filters.append(f"view_date >= '{since.isoformat()}'")
        if state:
            filters.append(f"uf = '{state.upper()}'")
        if biome:
            filters.append(f"bioma = '{biome}'")
        if classname:
            filters.append(f"classname = '{classname}'")

        try:
            raw = await self._wfs_get_feature(
                cql_filter=" AND ".join(filters) if filters else None,
                count=count,
            )
        except Exception as exc:
            import httpx
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
                # 400 often means the biome/state filter has no matching features in this layer
                return []
            raise
        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, DETERAlert)

    async def fetch_recent_deforestation(
        self,
        days: int = 30,
        state: str | None = None,
    ) -> list[DETERAlert]:
        """Shortcut: deforestation alerts only, for the past *days*."""
        from datetime import timedelta

        since = date.today() - timedelta(days=days)
        return await self.fetch_alerts_by_region(
            state=state,
            classname="DESMATAMENTO_VEG",
            since=since,
            count=1000,
        )

    async def fetch_time_series(
        self,
        state: str | None = None,
        biome: str | None = None,
        start: date | None = None,
        end: date | None = None,
        count: int = 5000,
    ) -> list[DETERAlert]:
        """Fetch a larger time-series window for trend analysis."""
        params: dict[str, Any] = {
            "state": state,
            "biome": biome,
            "start": start,
            "end": end,
            "count": count,
            "_method": "time_series",
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [DETERAlert.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if start:
            filters.append(f"view_date >= '{start.isoformat()}'")
        if end:
            filters.append(f"view_date <= '{end.isoformat()}'")
        if state:
            filters.append(f"uf = '{state.upper()}'")
        if biome:
            filters.append(f"bioma = '{biome}'")

        try:
            raw = await self._wfs_get_feature(
                cql_filter=" AND ".join(filters) if filters else None,
                count=count,
            )
        except Exception as exc:
            import httpx
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
                return []
            raise
        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, DETERAlert)


# ------------------------------------------------------------------ #
# Synchronous convenience wrappers (Streamlit-safe)                    #
# ------------------------------------------------------------------ #

@async_safe
async def _fetch_alerts_async(
    state: str | None,
    biome: str | None,
    classname: str | None,
    since: date | None,
    count: int,
) -> list[DETERAlert]:
    async with DETERClient() as client:
        return await client.fetch_alerts_by_region(state, biome, classname, since, count)


@async_safe
async def _fetch_recent_async(days: int, state: str | None) -> list[DETERAlert]:
    async with DETERClient() as client:
        return await client.fetch_recent_deforestation(days, state)


@async_safe
async def _fetch_series_async(
    state: str | None,
    biome: str | None,
    start: date | None,
    end: date | None,
    count: int,
) -> list[DETERAlert]:
    async with DETERClient() as client:
        return await client.fetch_time_series(state, biome, start, end, count)


def fetch_deter_alerts(
    state: str | None = None,
    biome: str | None = None,
    classname: str | None = None,
    since: date | None = None,
    count: int = 500,
) -> list[DETERAlert]:
    return _fetch_alerts_async(state, biome, classname, since, count)  # type: ignore[return-value]


def fetch_recent_deforestation(days: int = 30, state: str | None = None) -> list[DETERAlert]:
    return _fetch_recent_async(days, state)  # type: ignore[return-value]


def fetch_deter_time_series(
    state: str | None = None,
    biome: str | None = None,
    start: date | None = None,
    end: date | None = None,
    count: int = 5000,
) -> list[DETERAlert]:
    return _fetch_series_async(state, biome, start, end, count)  # type: ignore[return-value]


# ------------------------------------------------------------------ #
# Multi-biome routing                                                   #
# ------------------------------------------------------------------ #

@async_safe
async def _fetch_multi_biome_async(
    biome_ids: list[str],
    state: str | None,
    start: date | None,
    end: date | None,
    count: int,
) -> list[DETERAlert]:
    """Fetch DETER alerts across all biome-specific layers and merge results."""
    settings = get_settings()
    endpoint_map = {
        "amazonia": settings.inpe_deter_endpoint,
        "cerrado":  settings.inpe_deter_cerrado_endpoint,
    }
    results: list[DETERAlert] = []
    for biome_id in biome_ids:
        layer = _DETER_BIOME_LAYERS.get(biome_id)
        if not layer:
            continue  # no DETER layer for this biome (PRODES-only)
        endpoint = endpoint_map[biome_id]
        async with DETERClient(endpoint=endpoint, layer=layer) as client:
            alerts = await client.fetch_time_series(
                state=state, start=start, end=end, count=count
            )
        # Inject biome name so client-side filtering works
        display = _BIOME_DISPLAY.get(biome_id, biome_id)
        for a in alerts:
            if not a.biome:
                a.biome = display
        results.extend(alerts)
    return results


def fetch_deter_for_biomes(
    biome_ids: list[str],
    state: str | None = None,
    start: date | None = None,
    end: date | None = None,
    count: int = 5000,
) -> list[DETERAlert]:
    """Fetch DETER time-series across the given biomes, routing to the correct layer per biome."""
    return _fetch_multi_biome_async(biome_ids, state, start, end, count)  # type: ignore[return-value]
