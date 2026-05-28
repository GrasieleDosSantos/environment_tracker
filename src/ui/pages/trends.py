"""Tendências Ambientais / Environmental Trends (US5).

Provides a configurable time-series analysis view for fire and deforestation
data: trend line with direction indicator, Savitzky-Golay smoothing overlay,
side-by-side period comparison panel, and CSV / PDF export.

Data is fetched via the existing INPE clients and cached with ``st.cache_data``
(24 h TTL) using primitive-type cache keys to guarantee pickle-safety.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config.constants import BIOMES, STATES
from src.services.analysis.trend_analyzer import (
    TrendInfo,
    calculate_trend,
    compare_periods,
    deforestation_monthly_series,
    smoothed_series,
    trend_line_series,
)
from src.services.data_export import export_csv, export_pdf
from src.ui.components.filters import render_biome_filter, render_region_filter
from src.ui.components.status_indicators import (
    render_data_source_caption,
    render_error_message,
    render_freshness_badge,
)
from src.ui.styles import PALETTE

Metric = Literal["fire", "deforestation"]

# ------------------------------------------------------------------ #
# Page header                                                           #
# ------------------------------------------------------------------ #

st.title("Tendências Ambientais / Environmental Trends")
st.caption(
    "Análise temporal de indicadores ambientais por bioma e região — "
    "até 24 meses de histórico INPE. / "
    "Time-series analysis of environmental indicators by biome and region — "
    "up to 24 months of INPE history."
)

# ------------------------------------------------------------------ #
# Sidebar filters                                                        #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.header("Filtros / Filters")

    metric: Metric = st.radio(  # type: ignore[assignment]
        "Indicador / Indicator",
        options=["fire", "deforestation"],
        format_func=lambda m: "🔥 Focos de Queimada" if m == "fire" else "🌳 Desmatamento DETER",
        key="trends_metric",
    )

    selected_biomes: list[str] = render_biome_filter()
    selected_states: list[str] = render_region_filter()

    st.divider()
    st.subheader("Período / Date Range")

    _today = date.today()
    _max_start = _today - timedelta(days=30)
    _default_start = _today - timedelta(days=365 * 2)

    col_s, col_e = st.columns(2)
    with col_s:
        period_start: date = st.date_input(
            "Início / Start",
            value=_default_start,
            max_value=_max_start,
            key="trends_start",
        )  # type: ignore[assignment]
    with col_e:
        period_end: date = st.date_input(
            "Fim / End",
            value=_today,
            min_value=period_start + timedelta(days=30),
            max_value=_today,
            key="trends_end",
        )  # type: ignore[assignment]

    show_smoothed = st.checkbox("Mostrar linha suavizada / Show smoothed line", value=True, key="trends_smooth")
    show_trend = st.checkbox("Mostrar linha de tendência / Show trend line", value=True, key="trends_trendline")

    st.divider()
    st.subheader("Comparar períodos / Compare periods")
    enable_comparison = st.checkbox("Habilitar comparação / Enable comparison", key="trends_compare")

    if enable_comparison:
        comp_mid: date = period_start + (period_end - period_start) // 2
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            cmp_a_start: date = st.date_input(
                "Início A / Start A", value=period_start,
                min_value=period_start, max_value=period_end,
                key="trends_cmp_a_start",
            )  # type: ignore[assignment]
        with col_a2:
            cmp_a_end: date = st.date_input(
                "Fim A / End A", value=comp_mid,
                min_value=period_start, max_value=period_end,
                key="trends_cmp_a_end",
            )  # type: ignore[assignment]
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            cmp_b_start: date = st.date_input(
                "Início B / Start B", value=comp_mid,
                min_value=period_start, max_value=period_end,
                key="trends_cmp_b_start",
            )  # type: ignore[assignment]
        with col_b2:
            cmp_b_end: date = st.date_input(
                "Fim B / End B", value=period_end,
                min_value=period_start, max_value=period_end,
                key="trends_cmp_b_end",
            )  # type: ignore[assignment]


# ------------------------------------------------------------------ #
# Cached data loaders                                                   #
# ------------------------------------------------------------------ #

@st.cache_data(ttl=86400, show_spinner=False)
def _load_fire_monthly(
    state: str | None,
    biome_name: str | None,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    """Load monthly fire hotspot counts using WFS resultType=hits.

    Returns serialisable dicts with keys 'month' (ISO string) and 'count'.
    Uses hits queries instead of downloading individual records, so there is
    no count-cap truncation even for unfiltered Brazil-wide queries.
    """
    from src.services.inpe_integration.fogo_client import fetch_fire_monthly_counts
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    try:
        rows = fetch_fire_monthly_counts(
            start=start,
            end=end,
            state=state,
            biome=biome_name,
        )
        return [{"month": r["month"].isoformat(), "count": r["count"]} for r in rows]
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def _load_deter(
    state: str | None,
    biome_id: str | None,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    """Load DETER alerts, routing to the correct biome-specific WFS layer.

    DETER has separate layers per biome (deter-amz, deter-cerrado). Those
    layers do NOT expose a ``bioma`` CQL-filterable column — the biome is
    implicit in the layer itself. We use ``fetch_deter_for_biomes`` when a
    biome is selected so we hit the right layer without a biome CQL filter.
    For unfiltered (all-Brazil) queries we fall back to time_series which
    queries the Amazônia layer as the broadest available dataset.
    """
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    try:
        if biome_id:
            from src.services.inpe_integration.deter_client import fetch_deter_for_biomes
            alerts = fetch_deter_for_biomes(
                biome_ids=[biome_id], state=state, start=start, end=end
            )
        else:
            from src.services.inpe_integration.deter_client import fetch_deter_time_series
            alerts = fetch_deter_time_series(state=state, biome=None, start=start, end=end)
        return [a.model_dump() for a in alerts]
    except Exception:
        return []


def _reconstruct_alerts(raw: list[dict]) -> list:
    from src.services.inpe_integration.deter_client import DETERAlert
    return [DETERAlert.model_validate(r) for r in raw]


# ------------------------------------------------------------------ #
# Load data                                                             #
# ------------------------------------------------------------------ #

single_state = selected_states[0] if len(selected_states) == 1 else None
single_biome_id = selected_biomes[0] if len(selected_biomes) == 1 else None
# For biome name filter when multiple biomes: use None (fetch all, filter client-side)
single_biome_name: str | None = None
if single_biome_id:
    single_biome_name = next((b["name"] for b in BIOMES if b["id"] == single_biome_id), None)

start_iso = period_start.isoformat()
end_iso = period_end.isoformat()

# Biomes covered by near-real-time DETER layers on TerraBrasilis.
# All other biomes rely on PRODES annual data only (not yet integrated).
_DETER_COVERED_BIOMES: frozenset[str] = frozenset({"amazonia", "cerrado"})

deter_coverage_warning: str | None = None
deter_state_note: str | None = None

with st.spinner("Carregando dados INPE… / Loading INPE data…"):
    if metric == "fire":
        # Use monthly count queries (resultType=hits) — no per-record download,
        # so count-cap truncation never occurs even for unfiltered Brazil.
        # Multi-state / multi-biome: pass the first match or None; the hits
        # query is lightweight enough to run per-state if needed, but for
        # trends the regional label already scopes the question adequately.
        raw_counts = _load_fire_monthly(single_state, single_biome_name, start_iso, end_iso)
        if raw_counts:
            monthly_df = pd.DataFrame(raw_counts)
            monthly_df["month"] = pd.to_datetime(monthly_df["month"])
            monthly_df = monthly_df.sort_values("month").reset_index(drop=True)
        else:
            monthly_df = pd.DataFrame(columns=["month", "count"])
        value_col = "count"
        y_label = "Focos de calor / Fire hotspots"
        source_label = "BDQueimadas — INPE"

    else:
        # Check DETER biome coverage before loading
        if single_biome_id and single_biome_id not in _DETER_COVERED_BIOMES:
            biome_display = next((b["name"] for b in BIOMES if b["id"] == single_biome_id), single_biome_id)
            covered_names = ", ".join(
                b["name"] for b in BIOMES if b["id"] in _DETER_COVERED_BIOMES
            )
            deter_coverage_warning = (
                f"O sistema DETER não disponibiliza dados de desmatamento para o bioma "
                f"**{biome_display}**. O monitoramento DETER cobre apenas: {covered_names}. "
                f"Para os demais biomas, os dados anuais do PRODES estão em integração futura.\n\n"
                f"The DETER system does not provide deforestation data for the **{biome_display}** "
                f"biome. DETER monitoring covers only: {covered_names}. "
                f"Annual PRODES data for other biomes is planned for a future release."
            )
            monthly_df = pd.DataFrame(columns=["area_km2"])
        else:
            raw = _load_deter(single_state, single_biome_id, start_iso, end_iso)
            records = _reconstruct_alerts(raw)

            if len(selected_states) > 1:
                records = [a for a in records if a.state in selected_states]
            if len(selected_biomes) > 1:
                allowed_names = {b["name"].lower() for b in BIOMES if b["id"] in selected_biomes}
                records = [a for a in records if (a.biome or "").lower() in allowed_names]

            monthly_df = deforestation_monthly_series(records)

            # If we got nothing and states were the only filter, the state(s)
            # likely lie outside Amazônia/Cerrado — explain rather than error.
            if monthly_df.empty and selected_states and not single_biome_id:
                state_names = ", ".join(STATES.get(s, s) for s in selected_states)
                covered_names = ", ".join(
                    b["name"] for b in BIOMES if b["id"] in _DETER_COVERED_BIOMES
                )
                deter_state_note = (
                    f"Nenhum dado DETER encontrado para **{state_names}**. "
                    f"O sistema DETER monitora desmatamento apenas nos biomas {covered_names}. "
                    f"Estados fora dessas áreas (ex: Mata Atlântica, Caatinga, Pampa, Pantanal) "
                    f"não possuem cobertura DETER. Tente selecionar um bioma no filtro ao lado.\n\n"
                    f"No DETER data found for **{state_names}**. "
                    f"DETER monitors deforestation only in the {covered_names} biomes. "
                    f"States outside these areas (e.g. Atlantic Forest, Caatinga, Pampa, Pantanal) "
                    f"have no DETER coverage. Try selecting a biome in the sidebar filter."
                )

        value_col = "area_km2"
        y_label = "Área desmatada km² / Deforested area km²"
        source_label = "DETER — INPE"

# ------------------------------------------------------------------ #
# Region label                                                          #
# ------------------------------------------------------------------ #

region_parts: list[str] = []
if selected_biomes:
    region_parts += [b["name"] for b in BIOMES if b["id"] in selected_biomes]
if selected_states:
    region_parts += [STATES.get(s, s) for s in selected_states]
region_label = ", ".join(region_parts) if region_parts else "Brasil"

# ------------------------------------------------------------------ #
# Trend computation                                                     #
# ------------------------------------------------------------------ #

trend_info: TrendInfo | None = None
if not monthly_df.empty and len(monthly_df) >= 2:
    trend_info = calculate_trend(monthly_df, date_col="month", value_col=value_col)

# ------------------------------------------------------------------ #
# Direction indicator                                                   #
# ------------------------------------------------------------------ #

def _direction_badge(info: TrendInfo, metric_name: Metric) -> str:
    icon = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}[info.direction]
    # For deforestation, increasing is bad; for fire, also bad.
    colour = {
        "increasing": PALETTE["accent_red"],
        "decreasing": PALETTE["accent_green"],
        "stable": PALETTE["accent_yellow"],
    }[info.direction]
    pct = f"{abs(info.pct_change_over_period):.1f}%"
    label_pt = {"increasing": "Alta", "decreasing": "Baixa", "stable": "Estável"}[info.direction]
    label_en = {"increasing": "Rising", "decreasing": "Falling", "stable": "Stable"}[info.direction]
    sig = " *" if info.p_value < 0.05 else ""
    return (
        f"<span style='font-size:1.5rem'>{icon}</span> "
        f"<span style='color:{colour};font-weight:700'>{label_pt} / {label_en}</span> "
        f"({pct} over period{sig})"
    )


# ------------------------------------------------------------------ #
# Trend chart                                                           #
# ------------------------------------------------------------------ #

if deter_coverage_warning:
    st.info(deter_coverage_warning, icon="ℹ️")
elif deter_state_note:
    st.info(deter_state_note, icon="ℹ️")
elif monthly_df.empty:
    render_error_message("Sem dados para o período selecionado. / No data for the selected period.")
else:
    # KPI row
    if trend_info:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Média mensal / Monthly mean",
            f"{trend_info.mean_value:,.0f}",
            help="Média de valores mensais no período selecionado. / Average of monthly values over the selected period.",
        )
        k2.metric(
            "Total no período / Period total",
            f"{monthly_df[value_col].sum():,.0f}",
            help="Soma de todos os meses no período. / Sum of all months in the period.",
        )
        k3.metric("Meses / Months", f"{trend_info.n_points}")
        k4.metric(
            "R² (linear fit)",
            f"{trend_info.r_squared:.3f}",
            help="Goodness-of-fit of the linear trend. 1.0 = perfect fit.",
        )
        st.markdown(_direction_badge(trend_info, metric), unsafe_allow_html=True)
        if trend_info.p_value < 0.05:
            st.caption("* Tendência estatisticamente significativa (p < 0.05) / Statistically significant trend (p < 0.05)")
        st.divider()

    # Build figure manually for full control over overlays
    chart_title = (
        f"{'Focos de Queimada' if metric == 'fire' else 'Área Desmatada DETER'} — {region_label}"
    )
    fig = go.Figure()

    # Raw series
    fig.add_trace(go.Scatter(
        x=monthly_df["month"],
        y=monthly_df[value_col],
        name="Mensal / Monthly",
        line=dict(color=PALETTE["primary"], width=2),
        hovertemplate="<b>%{x|%b %Y}</b>: %{y:,.0f}<extra></extra>",
    ))

    if show_smoothed and len(monthly_df) >= 5:
        smooth_df = smoothed_series(monthly_df, date_col="month", value_col=value_col, window=5)
        if not smooth_df.empty:
            fig.add_trace(go.Scatter(
                x=smooth_df["month"],
                y=smooth_df["smoothed"],
                name="Suavizado / Smoothed",
                line=dict(color=PALETTE["accent_orange"], width=2, dash="dot"),
                hovertemplate="<b>Smoothed %{x|%b %Y}</b>: %{y:,.0f}<extra></extra>",
            ))

    if show_trend and len(monthly_df) >= 2:
        tl_df = trend_line_series(monthly_df, date_col="month", value_col=value_col)
        if not tl_df.empty:
            fig.add_trace(go.Scatter(
                x=tl_df["month"],
                y=tl_df["trend"],
                name="Tendência linear / Linear trend",
                line=dict(color=PALETTE["accent_red"], width=1.5, dash="dash"),
                hovertemplate="<b>Trend %{x|%b %Y}</b>: %{y:,.0f}<extra></extra>",
            ))

    _font = dict(family="Source Sans Pro, Arial, sans-serif", color=PALETTE["text"])
    fig.update_layout(
        title=dict(text=chart_title, font=dict(**_font, size=15), x=0.01),
        font=_font,
        paper_bgcolor=PALETTE["surface"],
        plot_bgcolor=PALETTE["surface_alt"],
        margin=dict(l=48, r=24, t=48, b=40),
        hovermode="x unified",
        xaxis=dict(showgrid=True, gridcolor="#E8F0EB", tickformat="%b %Y"),
        yaxis=dict(title=y_label, showgrid=True, gridcolor="#E8F0EB", rangemode="tozero"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, width="stretch", key="trends_main_chart")
    render_data_source_caption(source_label)

    # ------------------------------------------------------------------ #
    # Period comparison panel                                               #
    # ------------------------------------------------------------------ #

    if enable_comparison and len(monthly_df) >= 2:
        st.subheader("Comparação de Períodos / Period Comparison")

        cmp = compare_periods(
            monthly_df,
            period_a=(cmp_a_start, cmp_a_end),
            period_b=(cmp_b_start, cmp_b_end),
            date_col="month",
            value_col=value_col,
            label_a=f"A: {cmp_a_start:%d/%m/%Y}–{cmp_a_end:%d/%m/%Y}",
            label_b=f"B: {cmp_b_start:%d/%m/%Y}–{cmp_b_end:%d/%m/%Y}",
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Média mensal A / Monthly mean A", f"{cmp.mean_a:,.0f}")
        c2.metric("Média mensal B / Monthly mean B", f"{cmp.mean_b:,.0f}", delta=f"{cmp.absolute_change:+,.0f}")
        c3.metric("Variação / Change", f"{cmp.pct_change:+.1f}%" if cmp.pct_change is not None else "N/A")
        c4.metric("Direção / Direction", {
            "increasing": "📈 Alta",
            "decreasing": "📉 Baixa",
            "stable": "➡️ Estável",
        }[cmp.direction])

        if cmp.p_value is not None:
            sig_label = "significativa / significant" if cmp.p_value < 0.05 else "não significativa / not significant"
            st.caption(f"Mann-Whitney U test: p = {cmp.p_value:.4f} — diferença {sig_label}")

        # Mini comparison bar chart
        cmp_bar_df = pd.DataFrame({
            "Período / Period": [cmp.label_a, cmp.label_b],
            "Média mensal / Monthly mean": [cmp.mean_a, cmp.mean_b],
        })
        bar_fig = go.Figure(go.Bar(
            x=cmp_bar_df["Período / Period"],
            y=cmp_bar_df["Média mensal / Monthly mean"],
            marker_color=[PALETTE["primary"], PALETTE["accent_orange"]],
            hovertemplate="<b>%{x}</b>: %{y:,.0f}<extra></extra>",
        ))
        bar_fig.update_layout(
            paper_bgcolor=PALETTE["surface"],
            plot_bgcolor=PALETTE["surface_alt"],
            margin=dict(l=32, r=16, t=24, b=32),
            yaxis=dict(title=y_label, showgrid=True, gridcolor="#E8F0EB", rangemode="tozero"),
            showlegend=False,
            height=260,
        )
        st.plotly_chart(bar_fig, width="stretch", key="trends_comparison_bar")

    # ------------------------------------------------------------------ #
    # Export buttons                                                        #
    # ------------------------------------------------------------------ #

    st.subheader("Exportar / Export")
    exp_col1, exp_col2 = st.columns(2)

    export_df = monthly_df.copy()
    export_df.insert(0, "region", region_label)
    export_df.insert(0, "metric", metric)

    csv_bytes = export_csv(
        export_df,
        filename=f"inpe_{metric}_{region_label.replace(', ', '_')}_{start_iso}_{end_iso}.csv",
        title=f"{chart_title} — {start_iso} a {end_iso}",
    )
    with exp_col1:
        st.download_button(
            label="⬇️ Baixar CSV / Download CSV",
            data=csv_bytes,
            file_name=f"inpe_{metric}_{start_iso}_{end_iso}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with exp_col2:
        if st.button("⬇️ Baixar PDF / Download PDF", use_container_width=True, key="trends_pdf_btn"):
            with st.spinner("Gerando PDF… / Generating PDF…"):
                try:
                    pdf_bytes = export_pdf(
                        chart=fig,
                        data=export_df,
                        filename=f"inpe_{metric}_{start_iso}_{end_iso}.pdf",
                        title=chart_title,
                    )
                    st.download_button(
                        label="📄 Clique para baixar / Click to download",
                        data=pdf_bytes,
                        file_name=f"inpe_{metric}_{start_iso}_{end_iso}.pdf",
                        mime="application/pdf",
                        key="trends_pdf_download",
                        use_container_width=True,
                    )
                except Exception as exc:
                    st.error(f"Erro ao gerar PDF / PDF generation error: {exc}")
