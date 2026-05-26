"""Reusable Plotly chart components for environmental data visualisation.

All functions accept pandas DataFrames and return ``plotly.graph_objects.Figure``
objects. Caller is responsible for rendering via ``st.plotly_chart(fig, ...)``.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ui.styles import PALETTE

# ------------------------------------------------------------------ #
# Shared layout defaults                                                #
# ------------------------------------------------------------------ #

_FONT = dict(family="Source Sans Pro, Noto Sans, Arial, sans-serif", color=PALETTE["text"])
_MARGIN = dict(l=48, r=24, t=48, b=40)
_GRIDCOLOUR = "#E8F0EB"
_PAPER_BG = PALETTE["surface"]
_PLOT_BG = PALETTE["surface_alt"]


def _base_layout(title: str, source: str = "") -> dict:
    full_title = title
    if source:
        full_title += f"<br><sup style='color:{PALETTE['text_muted']}'>Fonte / Source: {source}</sup>"
    return dict(
        title=dict(text=full_title, font=dict(**_FONT, size=15), x=0.01),
        font=_FONT,
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_PLOT_BG,
        margin=_MARGIN,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
    )


# ------------------------------------------------------------------ #
# time_series_chart                                                     #
# ------------------------------------------------------------------ #

def time_series_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str,
    source: str = "",
    y_labels: dict[str, str] | None = None,
    colors: list[str] | None = None,
    y_axis_label: str = "",
    area: bool = False,
) -> go.Figure:
    """Line (or area-fill) chart for temporal data.

    Args:
        df: DataFrame with at least *x* and *y* columns.
        x: Column name for the x-axis (typically datetime/date).
        y: Column name(s) for the y-axis series.
        title: Chart title (Portuguese/English).
        source: INPE source attribution shown in subtitle.
        y_labels: Optional rename map ``{col: display_name}``.
        colors: Optional list of hex colours per series.
        y_axis_label: Y-axis label string.
        area: If True, fill area under the line.
    """
    if df.empty:
        return _empty_figure(title)

    ys = [y] if isinstance(y, str) else y
    default_colors = [
        PALETTE["primary"],
        PALETTE["accent_orange"],
        PALETTE["accent_red"],
        PALETTE["accent_yellow"],
    ]
    palette = colors or default_colors

    fig = go.Figure()
    for i, col in enumerate(ys):
        if col not in df.columns:
            continue
        label = (y_labels or {}).get(col, col)
        colour = palette[i % len(palette)]
        trace_kwargs: dict = dict(
            x=df[x],
            y=df[col],
            name=label,
            line=dict(color=colour, width=2),
            hovertemplate=f"<b>{label}</b>: %{{y:,.1f}}<extra></extra>",
        )
        if area:
            trace_kwargs["fill"] = "tozeroy"
            trace_kwargs["fillcolor"] = colour.rstrip(")") + "33)" if colour.startswith("rgb") else colour + "33"

        fig.add_trace(go.Scatter(**trace_kwargs))

    layout = _base_layout(title, source)
    layout["xaxis"] = dict(showgrid=True, gridcolor=_GRIDCOLOUR, tickformat="%b %Y")
    layout["yaxis"] = dict(
        title=y_axis_label,
        showgrid=True,
        gridcolor=_GRIDCOLOUR,
        rangemode="tozero",
    )
    fig.update_layout(**layout)
    return fig


# ------------------------------------------------------------------ #
# bar_comparison_chart                                                  #
# ------------------------------------------------------------------ #

def bar_comparison_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    source: str = "",
    color_col: str | None = None,
    orientation: str = "v",
    y_axis_label: str = "",
    top_n: int = 15,
) -> go.Figure:
    """Horizontal or vertical bar chart for categorical comparisons.

    Args:
        df: DataFrame with *x* and *y* columns.
        x: Category column (e.g. state code, biome name).
        y: Numeric value column.
        title: Chart title.
        source: INPE source attribution.
        color_col: Optional column to colour bars by.
        orientation: ``"v"`` (vertical) or ``"h"`` (horizontal).
        y_axis_label: Y-axis label.
        top_n: Maximum number of bars to show.
    """
    if df.empty:
        return _empty_figure(title)

    df_plot = df.head(top_n).copy()

    if orientation == "h":
        # Reverse so largest is on top
        df_plot = df_plot.iloc[::-1]
        fig = go.Figure(
            go.Bar(
                x=df_plot[y],
                y=df_plot[x],
                orientation="h",
                marker_color=PALETTE["primary"],
                hovertemplate=f"<b>%{{y}}</b>: %{{x:,.1f}}<extra></extra>",
            )
        )
        layout = _base_layout(title, source)
        layout["xaxis"] = dict(title=y_axis_label, showgrid=True, gridcolor=_GRIDCOLOUR)
        layout["yaxis"] = dict(showgrid=False)
    else:
        colour_seq = (
            px.colors.sequential.Greens_r
            if color_col is None
            else px.colors.qualitative.Set2
        )
        fig = px.bar(
            df_plot,
            x=x,
            y=y,
            color=color_col,
            color_discrete_sequence=colour_seq,
        )
        fig.update_traces(
            hovertemplate=f"<b>%{{x}}</b>: %{{y:,.1f}}<extra></extra>"
        )
        layout = _base_layout(title, source)
        layout["xaxis"] = dict(showgrid=False)
        layout["yaxis"] = dict(
            title=y_axis_label, showgrid=True, gridcolor=_GRIDCOLOUR, rangemode="tozero"
        )

    fig.update_layout(**layout)
    return fig


# ------------------------------------------------------------------ #
# spatial_heatmap                                                       #
# ------------------------------------------------------------------ #

def spatial_heatmap(
    df: pd.DataFrame,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    title: str = "Distribuição Espacial / Spatial Distribution",
    source: str = "",
    value_col: str | None = None,
    radius: int = 8,
) -> go.Figure:
    """Density heatmap of point data over Brazil.

    Args:
        df: DataFrame with *lat_col* and *lon_col* columns.
        lat_col: Latitude column name.
        lon_col: Longitude column name.
        title: Chart title.
        source: INPE source attribution.
        value_col: Optional weighting column (e.g. FRP for fire intensity).
        radius: Heatmap kernel radius in pixels.
    """
    if df.empty or lat_col not in df.columns or lon_col not in df.columns:
        return _empty_figure(title)

    df_clean = df.dropna(subset=[lat_col, lon_col])
    if df_clean.empty:
        return _empty_figure(title)

    z = df_clean[value_col] if value_col and value_col in df_clean.columns else None

    fig = go.Figure(
        go.Densitymapbox(
            lat=df_clean[lat_col],
            lon=df_clean[lon_col],
            z=z,
            radius=radius,
            colorscale=[
                [0.0, "rgba(255,255,100,0)"],
                [0.3, PALETTE["accent_yellow"]],
                [0.7, PALETTE["accent_orange"]],
                [1.0, PALETTE["accent_red"]],
            ],
            showscale=bool(z is not None),
            hovertemplate=(
                f"Lat: %{{lat:.3f}}<br>Lon: %{{lon:.3f}}"
                + (f"<br>{value_col}: %{{z:.1f}}" if z is not None else "")
                + "<extra></extra>"
            ),
        )
    )

    subtitle = f"<br><sup style='color:{PALETTE['text_muted']}'>Fonte / Source: {source}</sup>" if source else ""
    fig.update_layout(
        title=dict(
            text=title + subtitle,
            font=dict(**_FONT, size=15),
            x=0.01,
        ),
        mapbox=dict(
            style="carto-positron",
            center=dict(lat=-14.24, lon=-51.93),
            zoom=3.5,
        ),
        margin=dict(l=0, r=0, t=48, b=0),
        paper_bgcolor=_PAPER_BG,
        font=_FONT,
    )
    return fig


# ------------------------------------------------------------------ #
# Utility                                                               #
# ------------------------------------------------------------------ #

def _empty_figure(title: str) -> go.Figure:
    """Return a blank figure with a 'no data' annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text="Sem dados disponíveis / No data available",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color=PALETTE["text_muted"]),
    )
    fig.update_layout(
        title=dict(text=title, font=dict(**_FONT, size=15), x=0.01),
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_PLOT_BG,
        margin=_MARGIN,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig
