"""PRODES annual totals from the TerraBrasilis dashboard data files.

Summing ``area_km`` over the WFS yearly_deforestation layers is not viable:
each biome-year has 20k–70k polygons, the WFS caps responses at 50 000
features, and several layers fail when ``propertyName`` is used. The PRODES
dashboard publishes the same increments pre-aggregated per state as static
JSON (verified 2026-10-08 to match full WFS sums within 0.1%):

  files/data/prodes_<biome>.json            periods → features → areas (km²)
  files/config/loinames/prodes_<biome>.json  loiname gid → state name
  files/rates<YYYY>.json                     official Legal Amazon rates

Increments are the mapped polygon areas per biome. The official *rates*
exist only for the Legal Amazon and include INPE's cloud-cover correction,
so they are higher than the Amazon-biome increments for the same year.

Update freq:  annual (published ~November)
Cache TTL:    settings.cache_ttl_prodes (30 days)
"""

from __future__ import annotations

import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import httpx

from src.config.constants import BIOMES, STATES
from src.config.settings import get_settings
from src.services.inpe_integration.cache_manager import get_cache_manager
from src.services.inpe_integration.prodes_client import PRODESData
from src.utils.logging import get_logger

_log = get_logger(__name__)

_FILES_BASE = "https://terrabrasilis.dpi.inpe.br/app/prodes/dashboard/deforestation/files"

# Project biome id → dashboard file suffix
_DASHBOARD_BIOMES: dict[str, str] = {
    "amazonia":       "amazon",
    "cerrado":        "cerrado",
    "caatinga":       "caatinga",
    "mata_atlantica": "mata_atlantica",
    "pampa":          "pampa",
    "pantanal":       "pantanal",
}

_LOI_UF = 1              # loi gid for states (2=mun, 3=consunit, 4=indi are subsets)
_AREA_DEFORESTATION = 1  # area type for deforestation increments

_BIOME_DISPLAY: dict[str, str] = {b["id"]: b["name"] for b in BIOMES}

# 45 s keeps a single request well under Streamlit Cloud's WebSocket keepalive.
_TIMEOUT = httpx.Timeout(45.0, connect=10.0)


def _norm(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold().strip()


_STATE_BY_NAME: dict[str, str] = {_norm(name): code for code, name in STATES.items()}


def _uf_codes(loinames: dict[str, Any]) -> dict[int, str]:
    """Map dashboard state gids to UF codes."""
    codes: dict[int, str] = {}
    for loi in loinames.get("lois", []):
        if loi.get("gid") != _LOI_UF:
            continue
        for item in loi.get("loinames", []):
            code = _STATE_BY_NAME.get(_norm(item.get("loiname", "")))
            if code:
                codes[item["gid"]] = code
    return codes


def _state_year_table(data: dict[str, Any], uf_codes: dict[int, str]) -> dict[int, dict[str, float]]:
    """Return {year: {UF: km²}} from a dashboard data/rates file (state level only)."""
    table: dict[int, dict[str, float]] = {}
    for period in data.get("periods", []):
        year = period["endDate"]["year"]  # PRODES year runs Aug (year-1) – Jul (year)
        by_state = table.setdefault(year, {})
        for feature in period.get("features", []):
            if feature.get("loi") != _LOI_UF:
                continue
            code = uf_codes.get(feature.get("loiname"))
            if not code:
                continue
            for area in feature.get("areas", []):
                if area.get("type") == _AREA_DEFORESTATION:
                    by_state[code] = by_state.get(code, 0.0) + float(area.get("area") or 0.0)
    return table


def _cached_table(cache_key: str, build) -> dict[int, dict[str, float]]:
    cache = get_cache_manager()
    if cached := cache.get(cache_key):
        return {int(y): states for y, states in cached["years"].items()}
    table = build()
    cache.set(
        cache_key, "PRODES",
        {"years": {str(y): s for y, s in table.items()}},
        get_settings().cache_ttl_prodes,
    )
    return table


def _get_json(client: httpx.Client, path: str) -> dict[str, Any]:
    resp = client.get(f"{_FILES_BASE}/{path}")
    resp.raise_for_status()
    return resp.json()


def _biome_table(biome_id: str) -> dict[int, dict[str, float]]:
    suffix = _DASHBOARD_BIOMES[biome_id]

    def _build() -> dict[int, dict[str, float]]:
        with httpx.Client(timeout=_TIMEOUT) as client:
            loinames = _get_json(client, f"config/loinames/prodes_{suffix}.json")
            data = _get_json(client, f"data/prodes_{suffix}.json")
        return _state_year_table(data, _uf_codes(loinames))

    return _cached_table(f"prodes_dashboard:{biome_id}:v1", _build)


def fetch_prodes_annual_totals(
    biome_ids: list[str],
    state: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[PRODESData]:
    """Exact annual PRODES deforestation per biome (one record per biome-year).

    With *state*, totals cover that state's share of each biome and records
    carry ``state`` so callers filtering by state keep them. Biomes that fail
    to load are logged and skipped.
    """
    wanted = [b for b in biome_ids if b in _DASHBOARD_BIOMES]
    if not wanted:
        return []
    state = state.upper() if state else None

    def _load(biome_id: str) -> tuple[str, dict[int, dict[str, float]]]:
        try:
            return biome_id, _biome_table(biome_id)
        except Exception as exc:
            _log.warning("prodes_dashboard_error", biome=biome_id, error=str(exc))
            return biome_id, {}

    with ThreadPoolExecutor(max_workers=min(len(wanted), 4)) as pool:
        tables = list(pool.map(_load, wanted))

    records: list[PRODESData] = []
    for biome_id, table in tables:
        for year in sorted(table):
            if (start_year and year < start_year) or (end_year and year > end_year):
                continue
            by_state = table[year]
            if state:
                if state not in by_state:
                    continue
                area = by_state[state]
            else:
                area = sum(by_state.values())
            records.append(PRODESData(
                year=year, state=state, biome=_BIOME_DISPLAY.get(biome_id, biome_id), area_km2=area,
            ))
    return records


def fetch_legal_amazon_rates(
    start_year: int | None = None,
    end_year: int | None = None,
    state: str | None = None,
) -> dict[int, float]:
    """Official PRODES Legal Amazon deforestation rates {year: km²}.

    The dashboard names the file after the latest PRODES year
    (``rates2025.json``), so try the newest plausible names first.
    """
    def _build() -> dict[int, dict[str, float]]:
        with httpx.Client(timeout=_TIMEOUT) as client:
            loinames = _get_json(client, "config/loinames/prodes_legal_amazon.json")
            for year in range(date.today().year, date.today().year - 3, -1):
                try:
                    data = _get_json(client, f"rates{year}.json")
                except httpx.HTTPStatusError:
                    continue
                return _state_year_table(data, _uf_codes(loinames))
        raise RuntimeError("PRODES rates file not found")

    try:
        table = _cached_table("prodes_dashboard:legal_amazon_rates:v1", _build)
    except Exception as exc:
        _log.warning("prodes_rates_error", error=str(exc))
        return {}

    state = state.upper() if state else None
    rates: dict[int, float] = {}
    for year, by_state in table.items():
        if (start_year and year < start_year) or (end_year and year > end_year):
            continue
        if state:
            if state in by_state:
                rates[year] = by_state[state]
        else:
            rates[year] = sum(by_state.values())
    return dict(sorted(rates.items()))
