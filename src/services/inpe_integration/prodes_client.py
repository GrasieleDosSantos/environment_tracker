"""PRODES — annual Amazon deforestation program client.

WFS endpoint: terrabrasilis.dpi.inpe.br/geoserver/prodes-amz-nb/ows
Layer:        prodes-amz-nb:yearly_deforestation_biome
Update freq:  annual (published ~November)
Cache TTL:    30 days
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, model_validator

from src.config.settings import get_settings
from src.services.inpe_integration.base import BaseINPEClient
from src.services.inpe_integration.cache_manager import get_cache_manager
from src.utils.decorators import async_safe


class PRODESData(BaseModel):
    """One PRODES yearly deforestation record."""

    year: int | None = None
    state: str | None = None
    biome: str | None = None
    area_km2: float | None = None
    municipality: str | None = None
    geometry_type: str | None = None
    geometry_coordinates: Any = None

    @model_validator(mode="before")
    @classmethod
    def _from_feature(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        props = v.get("properties") or {}
        geom = v.get("geometry") or {}

        def _first(*keys: str) -> Any:
            for k in keys:
                if (val := props.get(k)) is not None:
                    return val
            return None

        raw_year = _first("year", "YEAR", "ano", "ANO")
        try:
            year = int(raw_year) if raw_year is not None else None
        except (ValueError, TypeError):
            year = None

        return {
            "year": year,
            "state": _first("state", "STATE", "uf", "UF"),
            "biome": _first("biome", "BIOME", "bioma", "BIOMA"),
            "area_km2": _first("area_km2", "AREA_KM2", "areakm2", "AREAKM2", "incremento"),
            "municipality": _first("municipio", "MUNICIPIO", "municipality"),
            "geometry_type": geom.get("type"),
            "geometry_coordinates": geom.get("coordinates"),
        }


class PRODESClient(BaseINPEClient):
    source_name = "PRODES"
    layer_name = "prodes-amz-nb:yearly_deforestation_biome"
    default_cache_ttl = 2592000  # 30 days

    def __init__(self) -> None:
        settings = get_settings()
        self.wfs_endpoint = settings.inpe_prodes_endpoint
        super().__init__(rate_limit=settings.rate_limit_prodes)
        self._cache = get_cache_manager()

    # ------------------------------------------------------------------ #
    # Public async API                                                      #
    # ------------------------------------------------------------------ #

    async def fetch_deforestation_by_period(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        state: str | None = None,
        biome: str | None = None,
        count: int = 2000,
    ) -> list[PRODESData]:
        """Fetch annual deforestation increments for a date range."""
        params: dict[str, Any] = {
            "start_year": start_year,
            "end_year": end_year,
            "state": state,
            "biome": biome,
            "count": count,
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [PRODESData.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if start_year:
            filters.append(f"year >= {start_year}")
        if end_year:
            filters.append(f"year <= {end_year}")
        if state:
            filters.append(f"state = '{state.upper()}'")
        if biome:
            filters.append(f"biome = '{biome}'")

        raw = await self._wfs_get_feature(
            cql_filter=" AND ".join(filters) if filters else None,
            count=count,
        )
        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, PRODESData)

    async def fetch_baseline_map(
        self,
        year: int | None = None,
        state: str | None = None,
    ) -> list[PRODESData]:
        """Fetch the accumulated deforestation baseline for a given year."""
        params: dict[str, Any] = {
            "year": year,
            "state": state,
            "_method": "baseline",
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [PRODESData.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if year:
            filters.append(f"year = {year}")
        if state:
            filters.append(f"state = '{state.upper()}'")

        raw = await self._wfs_get_feature(
            cql_filter=" AND ".join(filters) if filters else None,
            count=5000,
        )
        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, PRODESData)

    async def fetch_vintage_series(
        self,
        state: str | None = None,
        biome: str | None = None,
        years: int = 10,
    ) -> list[PRODESData]:
        """Fetch the last *years* of annual increments for trend analysis."""
        import datetime

        end_year = datetime.date.today().year - 1  # PRODES publishes previous year
        start_year = end_year - years + 1
        return await self.fetch_deforestation_by_period(
            start_year=start_year,
            end_year=end_year,
            state=state,
            biome=biome,
            count=5000,
        )


# ------------------------------------------------------------------ #
# Synchronous convenience wrappers (Streamlit-safe)                    #
# ------------------------------------------------------------------ #

@async_safe
async def _fetch_period_async(
    start_year: int | None,
    end_year: int | None,
    state: str | None,
    biome: str | None,
    count: int,
) -> list[PRODESData]:
    async with PRODESClient() as client:
        return await client.fetch_deforestation_by_period(
            start_year, end_year, state, biome, count
        )


@async_safe
async def _fetch_baseline_async(
    year: int | None, state: str | None
) -> list[PRODESData]:
    async with PRODESClient() as client:
        return await client.fetch_baseline_map(year, state)


@async_safe
async def _fetch_vintage_async(
    state: str | None, biome: str | None, years: int
) -> list[PRODESData]:
    async with PRODESClient() as client:
        return await client.fetch_vintage_series(state, biome, years)


def fetch_prodes_by_period(
    start_year: int | None = None,
    end_year: int | None = None,
    state: str | None = None,
    biome: str | None = None,
    count: int = 2000,
) -> list[PRODESData]:
    return _fetch_period_async(start_year, end_year, state, biome, count)  # type: ignore[return-value]


def fetch_prodes_baseline(
    year: int | None = None, state: str | None = None
) -> list[PRODESData]:
    return _fetch_baseline_async(year, state)  # type: ignore[return-value]


def fetch_prodes_vintage(
    state: str | None = None, biome: str | None = None, years: int = 10
) -> list[PRODESData]:
    return _fetch_vintage_async(state, biome, years)  # type: ignore[return-value]
