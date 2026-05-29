"""UI smoke test for Phase 4 filter components.

Run with: uv run streamlit run tests/ui_smoke.py

Verifies:
- FilterState model behaves correctly
- render_sidebar_filters() renders without error
- Selecting Cerrado + last 30 days produces correct FilterState
"""

import streamlit as st

from src.ui.components.filters import (
    FilterState,
    get_filter_state,
    init_filter_state,
    render_sidebar_filters,
)
from src.ui.components.status_indicators import (
    render_api_status,
    render_error_message,
    render_freshness_badge,
)
from src.ui.styles import inject_custom_css

st.set_page_config(page_title="UI Smoke Test — Phase 4", layout="wide")
inject_custom_css()

st.title("Phase 4 UI Smoke Test / Teste de Componentes")

# ------------------------------------------------------------------ #
# Sidebar filters                                                       #
# ------------------------------------------------------------------ #
fs = render_sidebar_filters()

# ------------------------------------------------------------------ #
# Main area: show current filter state                                  #
# ------------------------------------------------------------------ #
st.subheader("FilterState atual / Current FilterState")

col1, col2, col3 = st.columns(3)
col1.metric("Biomas selecionados", len(fs.biomes))
col2.metric("Estados selecionados", len(fs.states))

start, end = fs.resolve_dates()
col3.metric("Período / Period", f"{start} → {end}")

st.json(fs.model_dump(mode="json"))

# ------------------------------------------------------------------ #
# Status indicators demo                                                #
# ------------------------------------------------------------------ #
st.subheader("Status indicators / Indicadores de status")

from datetime import datetime, timedelta, timezone

now = datetime.now(tz=timezone.utc)
fresh_ts = now - timedelta(minutes=30)
stale_ts = now - timedelta(hours=14)
expired_ts = now - timedelta(hours=36)

c1, c2, c3 = st.columns(3)
with c1:
    st.caption("Fresh (< 12h)")
    render_freshness_badge(fresh_ts, label="FOGO")
with c2:
    st.caption("Stale (14h)")
    render_freshness_badge(stale_ts, label="DETER")
with c3:
    st.caption("Expired (36h)")
    render_freshness_badge(expired_ts, label="PRODES")

st.divider()
render_api_status({"DETER": True, "PRODES": True, "FOGO": False})

st.divider()
render_error_message(
    "Serviço TerraBrasilis temporariamente indisponível.",
    suggestion="Aguarde 5 minutos e tente novamente. / Wait 5 minutes and retry.",
    source="FOGO",
)

# ------------------------------------------------------------------ #
# Unit assertions (run headlessly via pytest too)                      #
# ------------------------------------------------------------------ #
def _assert_filter_state_logic() -> None:
    # Default state
    fs_default = FilterState()
    assert fs_default.is_empty()
    start, end = fs_default.resolve_dates()
    assert start < end

    # Cerrado + last 30 days
    fs_cerrado = FilterState(biomes=["cerrado"], date_preset="last_30_days")
    assert not fs_cerrado.is_empty()
    assert "cerrado" in fs_cerrado.biomes
    s, e = fs_cerrado.resolve_dates()
    from datetime import timedelta
    assert (e - s).days == 30

    # Custom date range
    from datetime import date
    fs_custom = FilterState(
        date_preset="custom",
        date_start=date(2026, 1, 1),
        date_end=date(2026, 3, 31),
    )
    s2, e2 = fs_custom.resolve_dates()
    assert s2 == date(2026, 1, 1)
    assert e2 == date(2026, 3, 31)

    # summary includes biome name
    assert "Cerrado" in fs_cerrado.summary()


_assert_filter_state_logic()
st.success("Todas as asserções passaram / All assertions passed")
