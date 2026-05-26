"""Painel de Dados Ambientais / Environmental Data Dashboard (US2).

KPI cards + time-series + geographic breakdown, all driven by sidebar filters.
Data loading is cached with st.cache_data to avoid re-fetching on every rerun.
"""

from __future__ import annotations

import streamlit as st

from src.config.constants import BIOMES
from src.services.analysis.aggregator import (
    aggregate_multi_source,
    deter_to_monthly_df,
    deter_to_state_df,
    fogo_to_daily_df,
    fogo_to_points_df,
    fogo_to_state_df,
)
from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot
from src.ui.components.charts import (
    bar_comparison_chart,
    spatial_heatmap,
    time_series_chart,
)
from src.services.inpe_integration.deter_client import _DETER_BIOME_LAYERS
from src.ui.components.filters import FilterState, render_sidebar_filters
from src.ui.components.status_indicators import (
    render_api_status,
    render_data_source_caption,
    render_error_message,
    render_freshness_badge,
)
from src.ui.styles import PALETTE

# ------------------------------------------------------------------ #
# Cached data loaders (primitives only — pickle-safe)                  #
# ------------------------------------------------------------------ #

@st.cache_data(ttl=86400, show_spinner=False)
def _load_deter(
    state: str | None,
    biome_ids_str: str | None,   # comma-joined biome IDs, e.g. "amazonia,cerrado"
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    from datetime import date
    from src.services.inpe_integration.deter_client import (
        fetch_deter_for_biomes,
        fetch_deter_time_series,
    )

    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)

    if biome_ids_str:
        biome_ids = biome_ids_str.split(",")
        alerts = fetch_deter_for_biomes(state=state, biome_ids=biome_ids, start=start, end=end)
    else:
        # No biome filter — default to Amazon only (largest / most active dataset)
        alerts = fetch_deter_time_series(state=state, start=start, end=end)
    return [a.model_dump(mode="json") for a in alerts]


@st.cache_data(ttl=14400, show_spinner=False)
def _load_fogo_48h(state: str | None, biome: str | None) -> list[dict]:
    from src.services.inpe_integration.fogo_client import fetch_current_hotspots

    hotspots = fetch_current_hotspots(state=state, biome=biome, count=10000)
    return [h.model_dump(mode="json") for h in hotspots]


@st.cache_data(ttl=14400, show_spinner=False)
def _load_fogo_period(
    state: str | None, biome: str | None, days: int
) -> list[dict]:
    from src.services.inpe_integration.fogo_client import fetch_fire_risk

    hotspots = fetch_fire_risk(state=state, biome=biome, days=min(days, 90))
    return [h.model_dump(mode="json") for h in hotspots]


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _single(values: list[str]) -> str | None:
    return values[0] if len(values) == 1 else None


def _filter_dicts(records: list[dict], key: str, values: list[str]) -> list[dict]:
    if not values:
        return records
    return [r for r in records if r.get(key) in values]


def _filter_biomes(records: list[dict], biome_ids: list[str]) -> list[dict]:
    """Case-insensitive client-side biome filter.

    WFS biome values vary in case ('CERRADO', 'Cerrado', 'cerrado').
    Normalise both sides to lower before comparing.
    """
    if not biome_ids:
        return records
    names_lower = {
        b["name"].lower()
        for bid in biome_ids
        for b in BIOMES
        if b["id"] == bid
    }
    return [r for r in records if (r.get("biome") or "").lower() in names_lower]


def _biome_names(biome_ids: list[str]) -> list[str]:
    return [
        b["name"]
        for bid in biome_ids
        for b in BIOMES
        if b["id"] == bid
    ]


# ------------------------------------------------------------------ #
# Page header                                                           #
# ------------------------------------------------------------------ #

st.title("📊 Painel Ambiental / Environmental Dashboard")
st.caption(
    "Dados INPE — DETER e FOGO em tempo quase real. "
    "/ INPE data — DETER and FOGO near real-time."
)

# Sidebar filters
fs: FilterState = render_sidebar_filters()
period_start, period_end = fs.resolve_dates()
period_days = (period_end - period_start).days

single_state = _single(fs.states)

# ------------------------------------------------------------------ #
# Data loading                                                          #
# ------------------------------------------------------------------ #

deter_error: str | None = None
fogo_error: str | None = None

with st.spinner("Carregando dados DETER... / Loading DETER data..."):
    biome_ids_str = ",".join(sorted(fs.biomes)) if fs.biomes else None
    try:
        deter_raw = _load_deter(
            single_state, biome_ids_str,
            period_start.isoformat(), period_end.isoformat(),
        )
        if len(fs.states) > 1:
            deter_raw = _filter_dicts(deter_raw, "state", fs.states)
    except Exception as exc:
        deter_raw = []
        deter_error = str(exc)

with st.spinner("Carregando dados FOGO... / Loading FOGO data..."):
    try:
        fogo_raw_48h = _load_fogo_48h(single_state, None)
        fogo_raw_period = _load_fogo_period(single_state, None, period_days)
        if len(fs.states) > 1:
            fogo_raw_48h = _filter_dicts(fogo_raw_48h, "state", fs.states)
            fogo_raw_period = _filter_dicts(fogo_raw_period, "state", fs.states)
        if fs.biomes:
            fogo_raw_48h = _filter_biomes(fogo_raw_48h, fs.biomes)
            fogo_raw_period = _filter_biomes(fogo_raw_period, fs.biomes)
    except Exception as exc:
        fogo_raw_48h = []
        fogo_raw_period = []
        fogo_error = str(exc)

# ------------------------------------------------------------------ #
# Aggregate                                                             #
# ------------------------------------------------------------------ #

deter_alerts = [DETERAlert.model_validate(r) for r in deter_raw]
fogo_48h = [FireHotspot.model_validate(r) for r in fogo_raw_48h]
fogo_period = [FireHotspot.model_validate(r) for r in fogo_raw_period]

_region_parts: list[str] = []
if fs.biomes:
    from src.config.constants import BIOMES as _BIOMES
    _region_parts.append(", ".join(
        next((b["name"] for b in _BIOMES if b["id"] == bid), bid) for bid in fs.biomes
    ))
if fs.states:
    _region_parts.append(", ".join(fs.states))
_region_label = " · ".join(_region_parts) if _region_parts else "Brasil"

snapshot = aggregate_multi_source(
    deter_alerts=deter_alerts,
    fogo_hotspots_48h=fogo_48h,
    fogo_hotspots_period=fogo_period,
    region_label=_region_label,
    period_start=period_start,
    period_end=period_end,
)

# ------------------------------------------------------------------ #
# Error banners                                                         #
# ------------------------------------------------------------------ #

if deter_error:
    render_error_message(
        deter_error,
        suggestion="Verifique a conectividade com o TerraBrasilis. / Check connectivity.",
        source="DETER",
    )
if fogo_error:
    render_error_message(
        fogo_error,
        suggestion="BDQueimadas pode estar temporariamente indisponível. / BDQueimadas may be temporarily unavailable.",
        source="FOGO",
    )

# ------------------------------------------------------------------ #
# KPI row                                                               #
# ------------------------------------------------------------------ #

st.subheader(
    f"Resumo: {snapshot.region_label} "
    f"· {period_start:%d/%m/%Y} – {period_end:%d/%m/%Y}"
)

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    label="🌳 Desmatamento / Deforestation",
    value=f"{snapshot.deforestation_km2:,.1f} km²",
    help="Área total de alertas DETER no período / Total DETER alert area in period",
)
k2.metric(
    label="🔥 Focos 48h / Hotspots 48h",
    value=f"{snapshot.fire_count_48h:,}",
    help="Focos de calor — últimas 48h, todos os satélites / Fire hotspots last 48h, all satellites",
)
k3.metric(
    label="📍 Alertas DETER",
    value=f"{snapshot.deforestation_count:,}",
    help="Número de polígonos de alerta DETER / Number of DETER alert polygons",
)

risk_colour = snapshot.fire_risk_colour
k4.markdown(
    f"<div style='border:1px solid {PALETTE['border']};border-radius:8px;"
    f"padding:0.75rem 1rem;background:{PALETTE['surface']}'>"
    f"<div style='font-size:0.78rem;color:{PALETTE['text_muted']};font-weight:500;"
    f"text-transform:uppercase;letter-spacing:.04em'>🚦 Risco de Fogo / Fire Risk</div>"
    f"<div style='font-size:1.6rem;font-weight:700;color:{risk_colour}'>"
    f"{snapshot.fire_risk_label_pt}</div></div>",
    unsafe_allow_html=True,
)

st.divider()

# ------------------------------------------------------------------ #
# DETER coverage note                                                   #
# ------------------------------------------------------------------ #

if fs.biomes:
    no_deter = [
        next(b["name"] for b in BIOMES if b["id"] == bid)
        for bid in fs.biomes
        if bid not in _DETER_BIOME_LAYERS
    ]
    if no_deter:
        biome_list = ", ".join(no_deter)
        st.info(
            f"ℹ️ **Monitoramento DETER não disponível para: {biome_list}.**  \n"
            f"O DETER (alertas em tempo quase real) cobre apenas Amazônia e Cerrado. "
            f"Para os demais biomas, os gráficos de desmatamento abaixo estarão vazios — "
            f"dados anuais do PRODES estarão disponíveis na página de Tendências.  \n"
            f"/ *DETER near-real-time alerts cover only Amazon and Cerrado. "
            f"For other biomes, deforestation charts below will be empty — "
            f"annual PRODES data will be available on the Trends page.*",
        )

# ------------------------------------------------------------------ #
# Time-series charts                                                    #
# ------------------------------------------------------------------ #

col_ts1, col_ts2 = st.columns(2)

with col_ts1:
    monthly_df = deter_to_monthly_df(deter_alerts)
    fig_defor = time_series_chart(
        df=monthly_df,
        x="month",
        y=["area_km2"],
        title="Área Desmatada por Mês / Monthly Deforestation Area",
        source="INPE DETER",
        y_labels={"area_km2": "Área (km²)"},
        y_axis_label="km²",
        area=True,
    )
    st.plotly_chart(fig_defor, use_container_width=True)
    if deter_alerts:
        render_freshness_badge(snapshot.fetched_at, label="DETER")

with col_ts2:
    daily_fire_df = fogo_to_daily_df(fogo_period)
    fig_fire = time_series_chart(
        df=daily_fire_df,
        x="date",
        y=["count"],
        title="Focos de Calor por Dia / Daily Fire Hotspots",
        source="INPE BDQueimadas",
        y_labels={"count": "Focos"},
        y_axis_label="Focos",
        colors=[PALETTE["accent_orange"]],
    )
    st.plotly_chart(fig_fire, use_container_width=True)
    if fogo_period:
        render_freshness_badge(snapshot.fetched_at, label="FOGO")

# ------------------------------------------------------------------ #
# Geographic breakdown                                                  #
# ------------------------------------------------------------------ #

col_geo1, col_geo2 = st.columns(2)

with col_geo1:
    state_defor_df = deter_to_state_df(deter_alerts)
    fig_states = bar_comparison_chart(
        df=state_defor_df,
        x="state",
        y="area_km2",
        title="Desmatamento por Estado / Deforestation by State",
        source="INPE DETER",
        orientation="h",
        y_axis_label="km²",
        top_n=10,
    )
    st.plotly_chart(fig_states, use_container_width=True)

with col_geo2:
    state_fire_df = fogo_to_state_df(fogo_period)
    fig_fire_state = bar_comparison_chart(
        df=state_fire_df,
        x="state",
        y="count",
        title="Focos por Estado / Hotspots by State",
        source="INPE BDQueimadas",
        orientation="h",
        y_axis_label="Focos",
        top_n=10,
    )
    st.plotly_chart(fig_fire_state, use_container_width=True)

# ------------------------------------------------------------------ #
# Density heatmap                                                       #
# ------------------------------------------------------------------ #

st.subheader("Mapa de Densidade de Focos / Fire Hotspot Density Map")

points_df = fogo_to_points_df(fogo_48h)
fig_heat = spatial_heatmap(
    df=points_df,
    title="Focos de Calor — Últimas 48h / Fire Hotspots — Last 48h",
    source="INPE BDQueimadas",
    value_col="frp",
)
st.plotly_chart(fig_heat, use_container_width=True)
render_data_source_caption(
    "INPE BDQueimadas",
    layer="dados_abertos:focos_48h_br_todosats",
    timestamp=snapshot.fetched_at,
)

# ------------------------------------------------------------------ #
# Footer: API status                                                    #
# ------------------------------------------------------------------ #

st.divider()
render_api_status(
    {
        "DETER": deter_error is None,
        "FOGO": fogo_error is None,
    },
    compact=True,
)
