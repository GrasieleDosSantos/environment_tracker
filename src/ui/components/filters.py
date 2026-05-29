"""Reusable filter components for sidebar filtering across dashboard and map pages.

Filter state is persisted in ``st.session_state.filter_state`` as a ``FilterState``
instance. All pages read from the same key so filters are preserved when navigating.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st
from pydantic import BaseModel, Field

from src.config.constants import BIOMES, LEGAL_AMAZON_STATES, STATE_CODES, STATES
from src.utils.date_utils import parse_date_range, today_brazil

# ------------------------------------------------------------------ #
# Filter state model                                                    #
# ------------------------------------------------------------------ #

_PRESET_LABELS: dict[str, str] = {
    "last_7_days": "Últimos 7 dias / Last 7 days",
    "last_30_days": "Últimos 30 dias / Last 30 days",
    "last_90_days": "Últimos 90 dias / Last 90 days",
    "last_6_months": "Últimos 6 meses / Last 6 months",
    "last_12_months": "Últimos 12 meses / Last 12 months",
    "custom": "Personalizado / Custom",
}

_PRESET_KEYS = list(_PRESET_LABELS.keys())


class FilterState(BaseModel):
    """Snapshot of all active filter selections."""

    states: list[str] = Field(default_factory=list)
    biomes: list[str] = Field(default_factory=list)
    date_preset: str = "last_30_days"
    date_start: date | None = None
    date_end: date | None = None

    def resolve_dates(self) -> tuple[date, date]:
        """Return (start, end) dates, resolving presets to calendar dates."""
        if self.date_preset == "custom":
            return parse_date_range(self.date_start, self.date_end)
        return parse_date_range(None, None, preset=self.date_preset)

    def is_empty(self) -> bool:
        return (
            not self.states
            and not self.biomes
            and self.date_preset == "last_30_days"
        )

    def summary(self) -> str:
        """Short human-readable summary of active filters (Portuguese)."""
        parts: list[str] = []
        if self.biomes:
            biome_names = [
                next((b["name"] for b in BIOMES if b["id"] == bid), bid)
                for bid in self.biomes
            ]
            parts.append(", ".join(biome_names))
        if self.states:
            parts.append(", ".join(self.states))
        start, end = self.resolve_dates()
        parts.append(f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}")
        return " · ".join(parts) if parts else "Todos os dados / All data"

    def to_session_dict(self) -> dict[str, Any]:
        """Return a plain dict for backwards-compatible storage in session_state."""
        return {
            "biome": self.biomes[0] if len(self.biomes) == 1 else None,
            "biomes": self.biomes,
            "state_code": self.states[0] if len(self.states) == 1 else None,
            "states": self.states,
            "date_preset": self.date_preset,
            "date_start": self.date_start,
            "date_end": self.date_end,
        }


# ------------------------------------------------------------------ #
# Session-state helpers                                                 #
# ------------------------------------------------------------------ #

_SESSION_KEY = "filter_state"


def init_filter_state() -> None:
    """Initialise filter_state in session_state if not already present."""
    if _SESSION_KEY not in st.session_state:
        st.session_state[_SESSION_KEY] = FilterState()


def get_filter_state() -> FilterState:
    """Return the current FilterState from session_state."""
    init_filter_state()
    raw = st.session_state[_SESSION_KEY]
    if isinstance(raw, FilterState):
        return raw
    # Migrate legacy dict format from app.py initialisation
    return FilterState(
        states=raw.get("states", [raw["state_code"]] if raw.get("state_code") else []),
        biomes=raw.get("biomes", [raw["biome"]] if raw.get("biome") else []),
        date_preset=raw.get("date_preset", "last_30_days"),
        date_start=raw.get("date_start"),
        date_end=raw.get("date_end"),
    )


def _save_filter_state(fs: FilterState) -> None:
    st.session_state[_SESSION_KEY] = fs


# ------------------------------------------------------------------ #
# Individual filter renderers                                           #
# ------------------------------------------------------------------ #

def render_biome_filter() -> list[str]:
    """Render a biome multiselect in the sidebar; return selected biome IDs."""
    fs = get_filter_state()

    options = [b["id"] for b in BIOMES]
    labels = {b["id"]: f"{b['name']} / {b['name_en']}" for b in BIOMES}

    selected = st.multiselect(
        "Bioma / Biome",
        options=options,
        default=fs.biomes,
        format_func=lambda x: labels.get(x, x),
        key="filter_biomes",
        help="Filtre por bioma brasileiro / Filter by Brazilian biome",
    )

    fs = fs.model_copy(update={"biomes": selected})
    _save_filter_state(fs)
    return selected


_AMAZONIA_LEGAL_KEY = "AMAZONIA_LEGAL"


def render_region_filter() -> list[str]:
    """Render a state multiselect; return state codes.

    'Amazônia Legal' is exposed as a virtual option that expands to the
    9 constituent state codes when selected.
    """
    fs = get_filter_state()

    state_options = [_AMAZONIA_LEGAL_KEY] + sorted(STATE_CODES)
    state_labels = {
        _AMAZONIA_LEGAL_KEY: "★ Amazônia Legal",
        **{code: f"{code} — {STATES[code]}" for code in sorted(STATE_CODES)},
    }

    selected_raw = st.multiselect(
        "Estado / State",
        options=state_options,
        default=fs.states,
        format_func=lambda x: state_labels.get(x, x),
        key="filter_states",
        help="Filtre por estado / Filter by state (UF)",
    )

    # Expand the virtual Amazônia Legal option into its constituent states
    if _AMAZONIA_LEGAL_KEY in selected_raw:
        other = [s for s in selected_raw if s != _AMAZONIA_LEGAL_KEY]
        selected = sorted(set(other) | set(LEGAL_AMAZON_STATES))
    else:
        selected = selected_raw

    fs = fs.model_copy(update={"states": selected})
    _save_filter_state(fs)
    return selected


def render_date_range_filter() -> tuple[date, date]:
    """Render date range controls (preset radio + optional calendar); return (start, end)."""
    fs = get_filter_state()

    preset = st.radio(
        "Período / Period",
        options=_PRESET_KEYS,
        format_func=lambda x: _PRESET_LABELS[x],
        index=_PRESET_KEYS.index(fs.date_preset) if fs.date_preset in _PRESET_KEYS else 1,
        key="filter_date_preset",
    )

    date_start = fs.date_start
    date_end = fs.date_end

    if preset == "custom":
        today = today_brazil()
        default_start = fs.date_start or (today.replace(day=1))
        default_end = fs.date_end or today

        c1, c2 = st.columns(2)
        with c1:
            date_start = st.date_input(
                "De / From",
                value=default_start,
                max_value=today,
                key="filter_date_start",
            )
        with c2:
            date_end = st.date_input(
                "Até / To",
                value=default_end,
                min_value=date_start,
                max_value=today,
                key="filter_date_end",
            )

    fs = fs.model_copy(
        update={"date_preset": preset, "date_start": date_start, "date_end": date_end}
    )
    _save_filter_state(fs)
    return fs.resolve_dates()


def render_clear_filters_button() -> bool:
    """Render a 'Clear filters' button; returns True if clicked."""
    fs = get_filter_state()
    if fs.is_empty():
        return False

    clicked = st.button(
        "Limpar filtros / Clear filters",
        key="btn_clear_filters",
        type="secondary",
        use_container_width=True,
    )
    if clicked:
        _save_filter_state(FilterState())
        st.rerun()
    return clicked


# ------------------------------------------------------------------ #
# Composite: render all filters in sidebar                             #
# ------------------------------------------------------------------ #

def render_sidebar_filters() -> FilterState:
    """Render all filter controls in the sidebar and return the current FilterState."""
    with st.sidebar:
        st.markdown("### Filtros / Filters")
        st.divider()

        render_biome_filter()
        st.divider()

        render_region_filter()
        st.divider()

        render_date_range_filter()
        st.divider()

        render_clear_filters_button()

        fs = get_filter_state()
        if not fs.is_empty():
            st.caption(f"Filtros ativos / Active filters: {fs.summary()}")

    return get_filter_state()
