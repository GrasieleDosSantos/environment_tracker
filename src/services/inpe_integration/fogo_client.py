"""FOGO / BDQueimadas — fire hotspot client.

Live-verified layer names (2026-05-26):
  focos_48h_br_todosats  → dados_abertos:focos_48h_br_todosats
  hoje                   → dados_abertos:focos_hoje_br_todosats
  historical (per year)  → dados_abertos:focos_YYYY_br_todosats
  current year           → dados_abertos:focos_ano_atual_br_todosats

Update freq:  every 3-6 hours
Cache TTL:    4 hours (48h / current queries); 24h for historical days
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, model_validator

from src.config.constants import STATES
from src.config.settings import get_settings
from src.services.inpe_integration.base import BaseINPEClient
from src.services.inpe_integration.cache_manager import get_cache_manager
from src.utils.decorators import async_safe

# Reverse map: full name (upper) → 2-letter code
_STATE_NAME_TO_CODE: dict[str, str] = {
    v.upper(): k for k, v in STATES.items()
}


def _estado_to_sigla(estado: str | None) -> str | None:
    if not estado:
        return None
    return _STATE_NAME_TO_CODE.get(estado.upper(), estado.upper()[:2])


class FireHotspot(BaseModel):
    """One fire hotspot from BDQueimadas WFS (dados_abertos workspace)."""

    latitude: float | None = None
    longitude: float | None = None
    detection_time: datetime | None = None
    date_pas: date | None = None       # data_pas — acquisition date, always populated
    state: str | None = None           # 2-letter sigla (derived from estado field)
    state_name: str | None = None      # full name as stored in WFS
    municipality: str | None = None
    biome: str | None = None
    satellite_source: str | None = None
    confidence: float | None = None    # risco_fogo 0–1
    frp: float | None = None           # Fire Radiative Power (MW)
    days_without_rain: int | None = None
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

        def _p(key: str) -> Any:
            return props.get(key)

        raw_dt = _p("data_hora_gmt") or _p("datahora") or _p("data_hora")
        parsed_dt: datetime | None = None
        if isinstance(raw_dt, str):
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed_dt = datetime.strptime(raw_dt[:19].replace("Z", ""), fmt.replace("Z", ""))
                    break
                except ValueError:
                    pass
        elif isinstance(raw_dt, datetime):
            parsed_dt = raw_dt

        estado_full = _p("estado") or _p("ESTADO")

        coords = geom.get("coordinates")
        lat = _p("latitude")
        lon = _p("longitude")
        if not lat and coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                lon, lat = float(coords[0]), float(coords[1])
            except (TypeError, ValueError):
                pass

        raw_pas = _p("data_pas") or _p("DATA_PAS")
        parsed_pas: date | None = None
        if isinstance(raw_pas, str):
            try:
                parsed_pas = date.fromisoformat(raw_pas[:10])
            except ValueError:
                pass
        elif isinstance(raw_pas, date):
            parsed_pas = raw_pas

        return {
            "latitude": lat,
            "longitude": lon,
            "detection_time": parsed_dt,
            "date_pas": parsed_pas,
            "state": _estado_to_sigla(estado_full),
            "state_name": estado_full,
            "municipality": _p("municipio") or _p("municipality"),
            "biome": _p("bioma") or _p("biome"),
            "satellite_source": _p("satelite") or _p("satellite"),
            "confidence": _p("risco_fogo"),
            "frp": _p("frp"),
            "days_without_rain": _p("numero_dias_sem_chuva"),
            "geometry_type": geom.get("type"),
            "geometry_coordinates": coords,
        }


class FOGOClient(BaseINPEClient):
    source_name = "FOGO"
    # Default layer for current 48h window (verified live 2026-05-26)
    layer_name = "dados_abertos:focos_48h_br_todosats"
    default_cache_ttl = 14400  # 4 hours

    def __init__(self) -> None:
        settings = get_settings()
        self.wfs_endpoint = settings.inpe_fogo_endpoint
        super().__init__(rate_limit=settings.rate_limit_fogo)
        self._cache = get_cache_manager()

    @staticmethod
    def _year_layer(year: int, ref_sat: bool = False) -> str:
        suffix = "satref" if ref_sat else "todosats"
        return f"dados_abertos:focos_{year}_br_{suffix}"

    # ------------------------------------------------------------------ #
    # Public async API                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estado_filter(state: str | None, states: list[str] | None) -> str | None:
        """Build a CQL estado predicate for single or multiple state codes."""
        if states and len(states) > 1:
            names = [f"'{STATES.get(s.upper(), s).upper()}'" for s in states]
            return f"estado IN ({', '.join(names)})"
        single = state or (states[0] if states else None)
        if single:
            return f"estado = '{STATES.get(single.upper(), single).upper()}'"
        return None

    async def fetch_current_hotspots(
        self,
        state: str | None = None,
        states: list[str] | None = None,
        biome: str | None = None,
        satellite: str | None = None,
        count: int = 5000,
    ) -> list[FireHotspot]:
        """Fetch hotspots from the pre-filtered 48-hour layer (no date filter needed)."""
        params: dict[str, Any] = {
            "state": state,
            "states": sorted(states) if states else None,
            "biome": biome,
            "satellite": satellite,
            "count": count,
            "_layer": self.layer_name,
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [FireHotspot.model_validate(f) for f in cached.get("features", [])]

        filters: list[str] = []
        if estado_pred := self._estado_filter(state, states):
            filters.append(estado_pred)
        if biome:
            filters.append(f"bioma = '{biome}'")
        if satellite:
            filters.append(f"satelite = '{satellite}'")

        raw = await self._wfs_get_feature(
            cql_filter=" AND ".join(filters) if filters else None,
            count=count,
        )
        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, FireHotspot)

    async def fetch_hotspots_by_date(
        self,
        target_date: date,
        state: str | None = None,
        biome: str | None = None,
        count: int = 10000,
    ) -> list[FireHotspot]:
        """Fetch all hotspots for a specific calendar day from the annual archive layer."""
        params: dict[str, Any] = {
            "date": target_date.isoformat(),
            "state": state,
            "biome": biome,
            "count": count,
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [FireHotspot.model_validate(f) for f in cached.get("features", [])]

        # Use per-year layer
        original_layer = self.layer_name
        self.layer_name = self._year_layer(target_date.year)

        day_str = target_date.isoformat()
        filters = [f"data_pas = '{day_str}'"]
        if state:
            state_name = STATES.get(state.upper(), state)
            filters.append(f"estado = '{state_name.upper()}'")
        if biome:
            filters.append(f"bioma = '{biome}'")

        try:
            raw = await self._wfs_get_feature(
                cql_filter=" AND ".join(filters),
                count=count,
            )
        finally:
            self.layer_name = original_layer

        ttl = 86400 if target_date < date.today() else self.default_cache_ttl
        self._cache.set(cache_key, self.source_name, raw, ttl)
        return self.parse_features(raw, FireHotspot)

    async def fetch_fire_risk(
        self,
        state: str | None = None,
        states: list[str] | None = None,
        biome: str | None = None,
        days: int = 7,
        count: int = 50000,
    ) -> list[FireHotspot]:
        """Fetch hotspots from the last *days* for risk-level aggregation.

        Uses the current-year layer with a CQL date filter.
        """
        from datetime import timedelta

        since = date.today() - timedelta(days=days)
        params: dict[str, Any] = {
            "since": since.isoformat(),
            "state": state,
            "states": sorted(states) if states else None,
            "biome": biome,
            "count": count,
            "_method": "risk",
        }
        cache_key = self.build_cache_key(params)
        if cached := self._cache.get(cache_key):
            return [FireHotspot.model_validate(f) for f in cached.get("features", [])]

        original_layer = self.layer_name
        self.layer_name = "dados_abertos:focos_ano_atual_br_todosats"

        filters = [f"data_pas >= '{since.isoformat()}'"]
        if estado_pred := self._estado_filter(state, states):
            filters.append(estado_pred)
        if biome:
            filters.append(f"bioma = '{biome}'")

        try:
            raw = await self._wfs_get_feature(
                cql_filter=" AND ".join(filters),
                count=count,
            )
        finally:
            self.layer_name = original_layer

        self._cache.set(cache_key, self.source_name, raw, self.default_cache_ttl)
        return self.parse_features(raw, FireHotspot)

    async def fetch_fire_monthly_counts(
        self,
        start: date,
        end: date,
        state: str | None = None,
        states: list[str] | None = None,
        biome: str | None = None,
    ) -> list[dict]:
        """Return monthly fire hotspot counts for a date range.

        Uses ``resultType=hits`` (WFS 2.0.0) so no feature data is downloaded
        — just the count per calendar month.  This avoids the ``count`` cap
        truncation that occurs when querying individual records for large areas
        like all of Brazil.

        Returns a list of ``{"month": date(year, month, 1), "count": int}``
        dicts, sorted ascending by month.  Months with zero hits are included
        so the trend series has no gaps.
        """
        current_year = date.today().year
        rows: list[dict] = []

        geo_pred = self._estado_filter(state, states) or ""
        biome_pred = f"bioma = '{biome}'" if biome else ""

        # Iterate month by month
        cur = date(start.year, start.month, 1)
        while cur <= end:
            month_end_day = (
                date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
                - __import__("datetime").timedelta(days=1)
            )
            range_start = max(start, cur)
            range_end = min(end, month_end_day)

            cache_key_data: dict[str, Any] = {
                "start": range_start.isoformat(),
                "end": range_end.isoformat(),
                "state": state,
                "states": sorted(states) if states else None,
                "biome": biome,
                "_method": "monthly_count",
            }
            cache_key = self.build_cache_key(cache_key_data)
            cached = self._cache.get(cache_key)
            # Only trust a cached entry that was written by a successful request
            # (marked with "ok": True).  Entries written by failed hits requests
            # lack this flag and will be overwritten with a fresh fetch.
            if cached and cached.get("ok") is True:
                rows.append({"month": cur, "count": cached["count"]})
                cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
                continue

            original_layer = self.layer_name
            self.layer_name = (
                "dados_abertos:focos_ano_atual_br_todosats"
                if cur.year == current_year
                else self._year_layer(cur.year)
            )

            filters = [
                f"data_pas >= '{range_start.isoformat()}'",
                f"data_pas <= '{range_end.isoformat()}'",
            ]
            if geo_pred:
                filters.append(geo_pred)
            if biome_pred:
                filters.append(biome_pred)

            try:
                n = await self._wfs_hits_count(cql_filter=" AND ".join(filters))
            except Exception:
                n = -1
            finally:
                self.layer_name = original_layer

            if n >= 0:
                # Cache successful results; mark with "ok" so stale error entries
                # are not reused next request.
                ttl = 86400 if range_end < date.today() else self.default_cache_ttl
                self._cache.set(cache_key, self.source_name, {"count": n, "ok": True}, ttl)
                rows.append({"month": cur, "count": n})
            else:
                # Request failed — do not cache; append 0 so the series has no gap
                rows.append({"month": cur, "count": 0})

            # Advance to next month
            cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)

        return rows

    async def fetch_fire_time_series(
        self,
        start: date,
        end: date,
        state: str | None = None,
        states: list[str] | None = None,
        biome: str | None = None,
        count_per_year: int = 50000,
    ) -> list[FireHotspot]:
        """Fetch hotspots across a multi-year date range.

        Splits the request by calendar year so each year's dedicated layer
        (``focos_YYYY_br_todosats``) is queried, with the current year using
        ``focos_ano_atual_br_todosats``.  Results are merged and returned as a
        flat list.

        This is the correct function for trend analysis that spans more than
        one calendar year.  ``fetch_fire_risk`` must NOT be used for this
        purpose because it is bound to the current-year layer.
        """
        current_year = date.today().year
        results: list[FireHotspot] = []

        # Iterate over each calendar year that overlaps [start, end]
        for year in range(start.year, end.year + 1):
            year_start = max(start, date(year, 1, 1))
            year_end = min(end, date(year, 12, 31))

            original_layer = self.layer_name
            self.layer_name = (
                "dados_abertos:focos_ano_atual_br_todosats"
                if year == current_year
                else self._year_layer(year)
            )

            params: dict[str, Any] = {
                "start": year_start.isoformat(),
                "end": year_end.isoformat(),
                "state": state,
                "states": sorted(states) if states else None,
                "biome": biome,
                "_method": "time_series",
            }
            cache_key = self.build_cache_key(params)
            if cached := self._cache.get(cache_key):
                results.extend(
                    FireHotspot.model_validate(f)
                    for f in cached.get("features", [])
                )
                self.layer_name = original_layer
                continue

            filters = [
                f"data_pas >= '{year_start.isoformat()}'",
                f"data_pas <= '{year_end.isoformat()}'",
            ]
            if estado_pred := self._estado_filter(state, states):
                filters.append(estado_pred)
            if biome:
                filters.append(f"bioma = '{biome}'")

            try:
                raw = await self._wfs_get_feature(
                    cql_filter=" AND ".join(filters),
                    count=count_per_year,
                )
            except Exception:
                raw = {"features": []}
            finally:
                self.layer_name = original_layer

            # Cache past years for 24h; current year for standard TTL
            ttl = 86400 if year < current_year else self.default_cache_ttl
            self._cache.set(cache_key, self.source_name, raw, ttl)
            results.extend(self.parse_features(raw, FireHotspot))

        return results


# ------------------------------------------------------------------ #
# Synchronous convenience wrappers (Streamlit-safe via @async_safe)    #
# ------------------------------------------------------------------ #

@async_safe
async def _fetch_current_async(
    state: str | None,
    states: list[str] | None,
    biome: str | None,
    satellite: str | None,
    count: int,
) -> list[FireHotspot]:
    async with FOGOClient() as client:
        return await client.fetch_current_hotspots(state, states, biome, satellite, count)


@async_safe
async def _fetch_by_date_async(
    target_date: date, state: str | None, biome: str | None, count: int
) -> list[FireHotspot]:
    async with FOGOClient() as client:
        return await client.fetch_hotspots_by_date(target_date, state, biome, count)


@async_safe
async def _fetch_risk_async(
    state: str | None,
    states: list[str] | None,
    biome: str | None,
    days: int,
    count: int,
) -> list[FireHotspot]:
    async with FOGOClient() as client:
        return await client.fetch_fire_risk(state, states, biome, days, count)


def fetch_current_hotspots(
    state: str | None = None,
    states: list[str] | None = None,
    biome: str | None = None,
    satellite: str | None = None,
    count: int = 5000,
) -> list[FireHotspot]:
    return _fetch_current_async(state, states, biome, satellite, count)  # type: ignore[return-value]


def fetch_hotspots_by_date(
    target_date: date | None = None,
    state: str | None = None,
    biome: str | None = None,
    count: int = 10000,
) -> list[FireHotspot]:
    if target_date is None:
        target_date = date.today()
    return _fetch_by_date_async(target_date, state, biome, count)  # type: ignore[return-value]


def fetch_fire_risk(
    state: str | None = None,
    states: list[str] | None = None,
    biome: str | None = None,
    days: int = 7,
    count: int = 50000,
) -> list[FireHotspot]:
    return _fetch_risk_async(state, states, biome, days, count)  # type: ignore[return-value]


@async_safe
async def _fetch_time_series_async(
    start: date,
    end: date,
    state: str | None,
    states: list[str] | None,
    biome: str | None,
    count_per_year: int,
) -> list[FireHotspot]:
    async with FOGOClient() as client:
        return await client.fetch_fire_time_series(start, end, state, states, biome, count_per_year)


def fetch_fire_time_series(
    start: date,
    end: date,
    state: str | None = None,
    states: list[str] | None = None,
    biome: str | None = None,
    count_per_year: int = 50000,
) -> list[FireHotspot]:
    """Fetch fire hotspots across a multi-year date range for trend analysis.

    Uses per-year WFS layers so historical data from previous calendar years
    is correctly included.  Use this instead of ``fetch_fire_risk`` whenever
    the query spans more than one year.
    """
    return _fetch_time_series_async(start, end, state, states, biome, count_per_year)  # type: ignore[return-value]


@async_safe
async def _fetch_monthly_counts_async(
    start: date,
    end: date,
    state: str | None,
    states: list[str] | None,
    biome: str | None,
) -> list[dict]:
    async with FOGOClient() as client:
        return await client.fetch_fire_monthly_counts(start, end, state, states, biome)


def fetch_fire_monthly_counts(
    start: date,
    end: date,
    state: str | None = None,
    states: list[str] | None = None,
    biome: str | None = None,
) -> list[dict]:
    """Return monthly fire hotspot counts using WFS resultType=hits.

    No individual records are downloaded — each month is a lightweight count
    query.  Use for trend analysis to avoid the count-cap truncation that
    occurs when fetching individual hotspot records for large regions.

    Returns a list of ``{"month": date, "count": int}`` dicts.
    """
    return _fetch_monthly_counts_async(start, end, state, states, biome)  # type: ignore[return-value]
