"""Status indicator components: data freshness badges, API health, error messages."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.config.constants import INPESource
from src.utils.date_utils import format_relative_age, is_stale


def render_freshness_badge(
    timestamp: datetime,
    label: str = "",
    warning_hours: int = 12,
) -> None:
    """Show a coloured badge indicating how fresh the data is.

    Green  → within warning_hours
    Yellow → stale but < 2× threshold
    Red    → very stale (> 2× threshold)
    """
    age_str = format_relative_age(timestamp)
    stale = is_stale(timestamp, warning_hours)
    very_stale = is_stale(timestamp, warning_hours * 2)

    if very_stale:
        colour = "#c0392b"
        icon = "🔴"
        status = "Desatualizado / Stale"
    elif stale:
        colour = "#e67e22"
        icon = "🟡"
        status = "Atenção / Warning"
    else:
        colour = "#27ae60"
        icon = "🟢"
        status = "Atualizado / Fresh"

    badge_text = f"{icon} {label + ' · ' if label else ''}{age_str} ({status})"
    st.markdown(
        f"<span style='font-size:0.8rem;color:{colour};font-weight:500'>{badge_text}</span>",
        unsafe_allow_html=True,
    )


def render_api_status(
    sources: dict[str, bool],
    compact: bool = False,
) -> None:
    """Render a status row for each INPE data source.

    Args:
        sources: mapping of source name → True (online) / False (offline).
        compact: if True, render as a single inline row instead of separate lines.
    """
    _DISPLAY = {
        INPESource.DETER.value: "DETER",
        INPESource.PRODES.value: "PRODES",
        INPESource.FOGO.value: "FOGO",
    }

    if compact:
        parts = []
        for name, online in sources.items():
            label = _DISPLAY.get(name, name)
            dot = "🟢" if online else "🔴"
            parts.append(f"{dot} {label}")
        st.markdown(
            "<span style='font-size:0.8rem'>" + " &nbsp; ".join(parts) + "</span>",
            unsafe_allow_html=True,
        )
    else:
        cols = st.columns(len(sources))
        for col, (name, online) in zip(cols, sources.items()):
            label = _DISPLAY.get(name, name)
            dot = "🟢" if online else "🔴"
            status = "Online" if online else "Offline"
            col.metric(
                label=f"{dot} {label}",
                value=status,
                delta=None,
            )


def render_error_message(
    msg: str,
    suggestion: str = "",
    source: str = "",
) -> None:
    """Render a formatted error card with an optional recovery suggestion.

    Args:
        msg: Primary error description (shown in Portuguese/English).
        suggestion: Optional recovery action for the user.
        source: Optional INPE source name that triggered the error.
    """
    source_prefix = f"[{source}] " if source else ""
    full_msg = f"{source_prefix}{msg}"

    with st.container(border=True):
        st.error(
            f"**Erro ao carregar dados / Error loading data**\n\n{full_msg}",
            icon="⚠️",
        )
        if suggestion:
            st.info(
                f"**Sugestão / Suggestion:** {suggestion}",
                icon="💡",
            )


def render_data_source_caption(
    source: str,
    layer: str = "",
    timestamp: datetime | None = None,
) -> None:
    """Render a small attribution caption below a chart or map panel."""
    parts = [f"Fonte / Source: **{source}**"]
    if layer:
        parts.append(f"camada / layer: `{layer}`")
    if timestamp:
        parts.append(format_relative_age(timestamp))

    st.caption(" · ".join(parts))
