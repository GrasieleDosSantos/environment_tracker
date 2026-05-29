"""PRODES — annual Amazon deforestation program client.

WFS endpoint: terrabrasilis.dpi.inpe.br/geoserver/prodes-amz-nb/ows
Layer:        prodes-amz-nb:yearly_deforestation_biome
Update freq:  annual (published ~November)
Cache TTL:    30 days
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, model_validator

from src.config.constants import BIOMES
from src.config.settings import get_settings
from src.services.inpe_integration.base import BaseINPEClient
from src.services.inpe_integration.cache_manager import get_cache_manager
from src.utils.decorators import async_safe

# All PRODES biome layers — verified live 2026-05-29.
# All use the same schema: area_km (not area_km2), image_date, state.
_PRODES_BIOME_LAYERS: dict[str, str] = {
    "amazonia":       "prodes-amazon-nb:yearly_deforestation_biome",
    "cerrado":        "prodes-cerrado-nb:yearly_deforestation",
    "caatinga":       "prodes-caatinga-nb:yearly_deforestation",
    "mata_atlantica": "prodes-mata-atlantica-nb:yearly_deforestation",
    "pampa":          "prodes-pampa-nb:yearly_deforestation",
    "pantanal":       "prodes-pantanal-nb:yearly_deforestation",
}

_PRODES_BIOME_ENDPOINTS: dict[str, str] = {
    biome_id: f"https://terrabrasilis.dpi.inpe.br/geoserver/{ws.split(':')[0]}/ows"
    for biome_id, ws in _PRODES_BIOME_LAYERS.items()
}

# Keep old names as aliases for backwards compatibility
_PRODES_NONAZ_LAYERS = _PRODES_BIOME_LAYERS
_PRODES_NONAZ_ENDPOINTS = _PRODES_BIOME_ENDPOINTS

_BIOME_DISPLAY: dict[str, str] = {b["id"]: b["name"] for b in BIOMES}


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
        if "properties" not in v and "geometry" not in v:
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
            # All PRODES layers return area_km; area_km2/incremento kept for legacy cache
            "area_km2": _first("area_km", "area_km2", "AREA_KM2", "areakm2", "AREAKM2", "incremento"),
            "municipality": _first("municipio", "MUNICIPIO", "municipality"),
            "geometry_type": geom.get("type"),
            "geometry_coordinates": geom.get("coordinates"),
        }


class PRODESClient(BaseINPEClient):
    source_name = "PRODES"
    layer_name = "prodes-amazon-nb:yearly_deforestation_biome"
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


# ------------------------------------------------------------------ #
# Non-Amazon PRODES (yearly_deforestation schema)                       #
# Schema: uid, state, year, area_km, main_class, class_name, image_date
# ------------------------------------------------------------------ #

class PRODESNonAmazonData(BaseModel):
    """PRODES yearly deforestation for non-Amazon biomes."""

    year: int | None = None
    state: str | None = None
    biome: str | None = None
    area_km2: float | None = None
    classname: str | None = None
    image_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_feature(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        if "properties" not in v and "geometry" not in v:
            return v
        props = v.get("properties") or {}

        raw_date = props.get("image_date")
        parsed_date: date | None = None
        if isinstance(raw_date, str):
            try:
                parsed_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                pass
        elif isinstance(raw_date, date):
            parsed_date = raw_date

        raw_year = props.get("year")
        try:
            year = int(raw_year) if raw_year is not None else (parsed_date.year if parsed_date else None)
        except (ValueError, TypeError):
            year = None

        return {
            "year": year,
            "state": props.get("state") or props.get("uf"),
            "biome": None,  # injected by caller based on which layer was queried
            "area_km2": props.get("area_km"),
            "classname": props.get("class_name") or props.get("main_class"),
            "image_date": parsed_date,
        }


class PRODESNonAmazonClient(BaseINPEClient):
    source_name = "PRODES"
    default_cache_ttl = 2592000  # 30 days

    def __init__(self, endpoint: str, layer: str) -> None:
        settings = get_settings()
        self.wfs_endpoint = endpoint
        self.layer_name = layer
        super().__init__(rate_limit=settings.rate_limit_prodes)
        self._cache = get_cache_manager()

    async def fetch_by_period(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        state: str | None = None,
        count: int = 2000,
    ) -> list[PRODESNonAmazonData]:
        params: dict[str, Any] = {
            "start_year": start_year, "end_year": end_year,
            "state": state, "count": count,
            "_layer": self.layer_name,
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [PRODESNonAmazonData.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if start_year:
            filters.append(f"year >= {start_year}")
        if end_year:
            filters.append(f"year <= {end_year}")
        if state:
            filters.append(f"state = '{state.upper()}'")

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
        return self.parse_features(raw, PRODESNonAmazonData)


@async_safe
async def _fetch_prodes_multi_biome_async(
    biome_ids: list[str],
    state: str | None,
    start_year: int | None,
    end_year: int | None,
    count: int,
) -> list[PRODESData]:
    """Fetch PRODES annual data across any combination of biomes, normalised to PRODESData.

    All six biomes (including Amazônia) now use PRODESNonAmazonClient since they
    share the same WFS schema (area_km, state, year, image_date).
    """
    results: list[PRODESData] = []

    for biome_id in biome_ids:
        layer = _PRODES_BIOME_LAYERS.get(biome_id)
        endpoint = _PRODES_BIOME_ENDPOINTS.get(biome_id)
        if not layer or not endpoint:
            continue

        async with PRODESNonAmazonClient(endpoint=endpoint, layer=layer) as client:
            raw_data = await client.fetch_by_period(
                start_year=start_year, end_year=end_year, state=state, count=count
            )

        display = _BIOME_DISPLAY.get(biome_id, biome_id)
        for r in raw_data:
            results.append(PRODESData(
                year=r.year,
                state=r.state,
                biome=display,
                area_km2=r.area_km2,
                municipality=None,
            ))

    return results


def fetch_prodes_for_biomes(
    biome_ids: list[str],
    state: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    count: int = 2000,
) -> list[PRODESData]:
    """Fetch PRODES annual deforestation across Amazon and all non-Amazon biomes."""
    return _fetch_prodes_multi_biome_async(biome_ids, state, start_year, end_year, count)  # type: ignore[return-value]
