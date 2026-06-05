"""Mapa Ambiental / Environmental Map page (US3).

Renders an interactive Folium map of Brazil with INPE fire and
deforestation layers.  Layer toggle controls live in the sidebar
next to the shared geo/date filters.  Zoom-to-region is applied
whenever the state selection changes.
"""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot
from src.ui.components.filters import FilterState, render_sidebar_filters
from src.ui.components.map import map_center_for_states, render_brazil_map
from src.ui.components.status_indicators import (
    render_api_status,
    render_data_source_caption,
    render_error_message,
    render_freshness_badge,
)

# ------------------------------------------------------------------ #
# Cached loaders (same pattern as dashboard.py)                        #
# ------------------------------------------------------------------ #

@st.cache_data(ttl=14400, show_spinner=False)
def _load_fogo(states_str: str | None, biome: str | None) -> list[dict]:
    from src.services.inpe_integration.fogo_client import fetch_current_hotspots

    states = states_str.split(",") if states_str else None
    single = states[0] if states and len(states) == 1 else None
    multi = states if states and len(states) > 1 else None
    return [
        h.model_dump(mode="json")
        for h in fetch_current_hotspots(state=single, states=multi, biome=biome, count=10000)
    ]


@st.cache_data(ttl=86400, show_spinner=False)
def _load_deter(
    state: str | None,
    biome_ids_str: str | None,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    from datetime import date

    from src.services.inpe_integration.deter_client import fetch_deter_for_biomes

    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)

    biome_ids = biome_ids_str.split(",") if biome_ids_str else ["amazonia", "cerrado"]
    alerts = fetch_deter_for_biomes(state=state, biome_ids=biome_ids, start=start, end=end)
    return [a.model_dump(mode="json") for a in alerts]


def _filter_dicts(records: list[dict], key: str, values: list[str]) -> list[dict]:
    if not values:
        return records
    return [r for r in records if r.get(key) in values]


# ------------------------------------------------------------------ #
# Page header                                                          #
# ------------------------------------------------------------------ #

st.title("🗺️ Mapa Ambiental / Environmental Map")
st.caption(
    "Visualização geográfica de focos de incêndio e alertas de desmatamento — INPE. "
    "/ Geographic view of fire hotspots and deforestation alerts — INPE."
)

# ------------------------------------------------------------------ #
# Sidebar: shared geo/date filters + layer toggles                     #
# ------------------------------------------------------------------ #

fs: FilterState = render_sidebar_filters()

with st.sidebar:
    st.divider()
    st.markdown("### Camadas / Layers")
    show_fires = st.toggle("🔥 Focos de Calor / Fire Hotspots", value=True)
    show_defor = st.toggle("🌳 Alertas DETER / Deforestation Alerts", value=True)
    show_biomes = st.toggle("Biomas / Biome Boundaries", value=False)

period_start, period_end = fs.resolve_dates()
single_state = fs.states[0] if len(fs.states) == 1 else None

# ------------------------------------------------------------------ #
# Data loading                                                         #
# ------------------------------------------------------------------ #

import threading as _threading
from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _as_completed

fogo_error: str | None = None
deter_error: str | None = None

fogo_states_str = ",".join(sorted(fs.states)) if fs.states else None
biome_ids_str = ",".join(sorted(fs.biomes)) if fs.biomes else None
_start_iso = period_start.isoformat()
_end_iso = period_end.isoformat()

_map_results: dict = {}
_map_done = _threading.Event()

def _load_map_data() -> None:
    with _TPE(max_workers=2) as pool:
        futures = {
            pool.submit(_load_fogo, fogo_states_str, None): "fogo",
            pool.submit(_load_deter, single_state, biome_ids_str, _start_iso, _end_iso): "deter",
        }
        for f in _as_completed(futures):
            key = futures[f]
            try:
                _map_results[key] = f.result()
            except Exception as exc:
                _map_results[key] = []
                _map_results[f"error_{key}"] = str(exc)
    _map_done.set()

_threading.Thread(target=_load_map_data, daemon=True).start()

_map_status = st.empty()
_map_ticks = 0
while not _map_done.wait(timeout=2):
    _map_status.caption(
        "⏳ Carregando dados INPE… / Loading INPE data…"
        if _map_ticks < 5
        else "🌐 Aguardando resposta do TerraBrasilis… / Waiting for TerraBrasilis…"
    )
    _map_ticks += 1
_map_status.empty()

fogo_raw = _map_results.get("fogo", [])
deter_raw = _map_results.get("deter", [])
fogo_error = _map_results.get("error_fogo")
deter_error = _map_results.get("error_deter")

if len(fs.states) > 1:
    deter_raw = _filter_dicts(deter_raw, "state", fs.states)

# Reconstruct model objects for the map component
fogo_hotspots: list[FireHotspot] = [FireHotspot.model_validate(r) for r in fogo_raw]
deter_alerts: list[DETERAlert] = [DETERAlert.model_validate(r) for r in deter_raw]

# ------------------------------------------------------------------ #
# Error banners                                                        #
# ------------------------------------------------------------------ #

if fogo_error:
    render_error_message(
        fogo_error,
        suggestion="BDQueimadas pode estar temporariamente indisponível. / BDQueimadas may be temporarily unavailable.",
        source="FOGO",
    )
if deter_error:
    render_error_message(
        deter_error,
        suggestion="Verifique a conectividade com o TerraBrasilis. / Check connectivity.",
        source="DETER",
    )

# ------------------------------------------------------------------ #
# Zoom-to-region: derive centre and zoom from active state filter      #
# ------------------------------------------------------------------ #

if fs.states:
    center, zoom = map_center_for_states(fs.states)
else:
    center, zoom = (-14.24, -51.93), 4

# ------------------------------------------------------------------ #
# Map                                                                  #
# ------------------------------------------------------------------ #

fmap = render_brazil_map(
    fire_hotspots=fogo_hotspots if show_fires else None,
    deter_alerts=deter_alerts if show_defor else None,
    show_fires=show_fires,
    show_deforestation=show_defor,
    show_biomes=show_biomes,
    highlight_states=fs.states or None,
    highlight_biomes=fs.biomes or None,
    center=center,
    zoom_start=zoom,
)

map_data = st_folium(
    fmap,
    key=f"brazil_map_{','.join(sorted(fs.states))}_{','.join(sorted(fs.biomes))}_{period_start}_{period_end}",
    use_container_width=True,
    height=600,
    returned_objects=[],
)

# ------------------------------------------------------------------ #
# Summary counts below the map                                         #
# ------------------------------------------------------------------ #

c1, c2 = st.columns(2)
c1.metric(
    "🔥 Focos 48h / Hotspots 48h",
    f"{len(fogo_hotspots):,}",
    help="Focos de calor nas últimas 48 h / Fire hotspots in the last 48 hours",
)
c2.metric(
    "🌳 Alertas DETER",
    f"{len(deter_alerts):,}",
    help="Polígonos de alerta DETER no período / DETER alert polygons in the selected period",
)

# ------------------------------------------------------------------ #
# Freshness + attribution                                              #
# ------------------------------------------------------------------ #

from datetime import datetime, timezone

_now = datetime.now(timezone.utc)

col_f1, col_f2 = st.columns(2)
with col_f1:
    if fogo_hotspots:
        render_freshness_badge(_now, label="FOGO 48h")
    else:
        st.caption("FOGO: sem dados / no data")
with col_f2:
    if deter_alerts:
        render_freshness_badge(_now, label="DETER")
    else:
        st.caption("DETER: sem dados / no data")

render_data_source_caption(
    "INPE BDQueimadas + TerraBrasilis",
    layer="focos_48h_br_todosats · deter_amz / deter_cerrado",
    timestamp=_now,
)

# ------------------------------------------------------------------ #
# Footer                                                               #
# ------------------------------------------------------------------ #

st.divider()
render_api_status(
    {"DETER": deter_error is None, "FOGO": fogo_error is None},
    compact=True,
)
