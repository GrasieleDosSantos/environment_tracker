"""Alertas Ambientais / Environmental Alerts (US4).

Displays auto-generated fire-outbreak and deforestation-spike alerts sourced
from INPE data.  Alerts are evaluated on page load (if none exist for today)
and persisted in SQLite so they survive page navigation.

Features:
- Alert list sorted by severity then recency
- Filter by alert type and status
- One-click dismiss (→ archived) and resolve actions
- Click-through link that pre-sets the map page filter to the alert's region
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import streamlit as st

from src.config.constants import AlertSeverity, AlertStatus, AlertType, BIOMES, STATES
from src.database.connection import get_db_session
from src.database.models import AlertDB
from src.ui.components.status_indicators import render_error_message
from src.ui.styles import PALETTE

# ------------------------------------------------------------------ #
# Severity display helpers                                              #
# ------------------------------------------------------------------ #

_SEVERITY_EMOJI: dict[str, str] = {
    AlertSeverity.CRITICAL: "🔴",
    AlertSeverity.HIGH: "🟠",
    AlertSeverity.MEDIUM: "🟡",
    AlertSeverity.LOW: "🟢",
}
_SEVERITY_COLOUR: dict[str, str] = {
    AlertSeverity.CRITICAL: "#C0392B",
    AlertSeverity.HIGH: "#E67E22",
    AlertSeverity.MEDIUM: "#F39C12",
    AlertSeverity.LOW: "#27AE60",
}
_SEVERITY_ORDER: dict[str, int] = {
    AlertSeverity.CRITICAL: 0,
    AlertSeverity.HIGH: 1,
    AlertSeverity.MEDIUM: 2,
    AlertSeverity.LOW: 3,
}
_TYPE_LABELS: dict[str, str] = {
    AlertType.FIRE_OUTBREAK:      "🔥 Surto de queimada / Fire outbreak",
    AlertType.DEFORESTATION_SPIKE: "🌳 Pico de desmatamento / Deforestation spike",
    AlertType.VEGETATION_LOSS:    "🌿 Perda de vegetação / Vegetation loss",
}
_STATUS_LABELS: dict[str, str] = {
    AlertStatus.ACTIVE:   "Ativo / Active",
    AlertStatus.ARCHIVED: "Arquivado / Archived",
    AlertStatus.RESOLVED: "Resolvido / Resolved",
}

# ------------------------------------------------------------------ #
# Page header                                                           #
# ------------------------------------------------------------------ #

st.title("🚨 Alertas Ambientais / Environmental Alerts")
st.caption(
    "Eventos ambientais críticos detectados pelo INPE — "
    "surtos de queimada e picos de desmatamento. "
    "/ Critical environmental events detected by INPE — "
    "fire outbreaks and deforestation spikes."
)

# ------------------------------------------------------------------ #
# Sidebar filters                                                        #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.header("Filtros / Filters")

    _all_types = list(_TYPE_LABELS.keys())
    _type_filter: list[str] = st.multiselect(
        "Tipo de alerta / Alert type",
        options=_all_types,
        default=_all_types,
        format_func=lambda t: _TYPE_LABELS.get(t, t),
        key="alerts_type_filter",
    )

    _all_statuses = list(_STATUS_LABELS.keys())
    _status_filter: list[str] = st.multiselect(
        "Status",
        options=_all_statuses,
        default=[AlertStatus.ACTIVE],
        format_func=lambda s: _STATUS_LABELS.get(s, s),
        key="alerts_status_filter",
    )

    _biome_filter: str | None = st.selectbox(
        "Bioma / Biome",
        options=[b["id"] for b in BIOMES],
        format_func=lambda b: next((x["name"] for x in BIOMES if x["id"] == b), b),
        index=None,
        placeholder="Selecione um bioma… / Select a biome…",
        key="alerts_biome_filter",
    )

    _state_filter: str | None = st.selectbox(
        "Estado / State",
        options=list(STATES.keys()),
        format_func=lambda s: f"{s} — {STATES.get(s, s)}",
        index=None,
        placeholder="Selecione um estado… / Select a state…",
        key="alerts_state_filter",
    )

    st.divider()

    _has_region = bool(_biome_filter or _state_filter)

    # Trigger a fresh alert check for the selected filters
    st.button(
        "🔍 Verificar alertas agora / Check alerts now",
        use_container_width=True,
        disabled=not _has_region,
        help=(
            None if _has_region
            else "Selecione um bioma ou estado para verificar alertas. / Select a biome or state first."
        ),
        on_click=lambda: st.session_state.update({"alerts_check_requested": True}),
    )

# ------------------------------------------------------------------ #
# Auto-check: run once per session if no alerts exist for today         #
# ------------------------------------------------------------------ #

def _count_today_alerts() -> int:
    today_start = datetime.now(tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).replace(tzinfo=None)
    with get_db_session() as db:
        from sqlalchemy import select, func
        count = db.execute(
            select(func.count()).select_from(AlertDB).where(
                AlertDB.detection_date >= today_start
            )
        ).scalar_one()
    return count


_check_requested = st.session_state.pop("alerts_check_requested", False)
_auto_checked = st.session_state.get("alerts_auto_checked", False)

if not _has_region:
    st.info(
        "Selecione um **bioma** ou **estado** na barra lateral para verificar alertas nessa região. "
        "/ Select a **biome** or **state** in the sidebar to check alerts for that region.",
        icon="📍",
    )
    # Reset auto-check flag so the check runs as soon as a region is selected
    st.session_state["alerts_auto_checked"] = False
elif _check_requested or not _auto_checked:
    _result: dict = {}
    _done = threading.Event()

    def _run_check() -> None:
        try:
            from src.services.analysis.alert_generator import run_alert_check
            new_alerts = run_alert_check(
                state=_state_filter or None,
                biome_id=_biome_filter or None,
            )
            _result["new"] = len(new_alerts)
        except Exception as exc:
            _result["error"] = str(exc)
        finally:
            _done.set()

    threading.Thread(target=_run_check, daemon=True).start()
    _spinner = st.empty()
    _tick = 0
    while not _done.wait(timeout=2):
        _spinner.caption(
            "⏳ Verificando alertas INPE… / Checking INPE alerts…"
            if _tick < 5 else
            "🌐 Aguardando TerraBrasilis… / Waiting for TerraBrasilis…"
        )
        _tick += 1
    _spinner.empty()

    st.session_state["alerts_auto_checked"] = True

    if "error" in _result:
        render_error_message(
            _result["error"],
            suggestion=(
                "Verifique a conectividade com o TerraBrasilis. "
                "/ Check connectivity with TerraBrasilis."
            ),
        )
    elif _result.get("new", 0) > 0:
        st.success(
            f"✅ {_result['new']} novo(s) alerta(s) gerado(s). "
            f"/ {_result['new']} new alert(s) generated."
        )

# ------------------------------------------------------------------ #
# Load alerts from DB                                                   #
# ------------------------------------------------------------------ #

def _load_alerts(
    types: list[str],
    statuses: list[str],
    biome_id: str | None,
    state_id: str | None,
    limit: int = 200,
) -> list[AlertDB]:
    with get_db_session() as db:
        from sqlalchemy import select
        stmt = select(AlertDB)
        if types:
            stmt = stmt.where(AlertDB.event_type.in_(types))
        if statuses:
            stmt = stmt.where(AlertDB.status.in_(statuses))
        if biome_id:
            stmt = stmt.where(AlertDB.biome_id == biome_id)
        if state_id:
            stmt = stmt.where(AlertDB.region_id == state_id)
        stmt = stmt.order_by(
            AlertDB.detection_date.desc()
        ).limit(limit)
        return list(db.execute(stmt).scalars().all())


alerts = _load_alerts(
    types=_type_filter,
    statuses=_status_filter,
    biome_id=_biome_filter or None,
    state_id=_state_filter or None,
)

# Sort client-side by severity first, then recency
alerts.sort(
    key=lambda a: (
        _SEVERITY_ORDER.get(a.severity_level, 99),
        -(a.detection_date.timestamp() if a.detection_date else 0),
    )
)

# ------------------------------------------------------------------ #
# Summary metrics                                                       #
# ------------------------------------------------------------------ #

_active = [a for a in alerts if a.status == AlertStatus.ACTIVE]
_critical = [a for a in _active if a.severity_level == AlertSeverity.CRITICAL]
_high = [a for a in _active if a.severity_level == AlertSeverity.HIGH]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Alertas ativos / Active", len(_active))
col2.metric("🔴 Críticos / Critical", len(_critical))
col3.metric("🟠 Altos / High", len(_high))
col4.metric("Total (filtrado)", len(alerts))

st.divider()

# ------------------------------------------------------------------ #
# Alert cards                                                           #
# ------------------------------------------------------------------ #

if not alerts:
    st.info(
        "Nenhum alerta encontrado com os filtros selecionados. "
        "/ No alerts found with the selected filters.",
        icon="ℹ️",
    )
else:
    for alert in alerts:
        severity = alert.severity_level
        emoji = _SEVERITY_EMOJI.get(severity, "⚪")
        colour = _SEVERITY_COLOUR.get(severity, "#6C757D")
        type_label = _TYPE_LABELS.get(alert.event_type, alert.event_type)
        status_label = _STATUS_LABELS.get(alert.status, alert.status)

        location_parts: list[str] = []
        if alert.biome_id:
            location_parts.append(
                next((b["name"] for b in BIOMES if b["id"] == alert.biome_id), alert.biome_id)
            )
        if alert.region_id:
            location_parts.append(STATES.get(alert.region_id, alert.region_id))
        location = " · ".join(location_parts) if location_parts else "Brasil"

        det_date = alert.detection_date.strftime("%d/%m/%Y %H:%M") if alert.detection_date else "—"

        with st.container(border=True):
            header_col, action_col = st.columns([3, 1])

            with header_col:
                st.markdown(
                    f"**{emoji} {type_label}** &nbsp;&nbsp; "
                    f'<span style="color:{colour}; font-weight:bold">{severity.upper()}</span> &nbsp; '
                    f'<span style="color:#6C757D; font-size:0.85em">{status_label}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"📍 {location} &nbsp;·&nbsp; 🗓 {det_date}")
                st.markdown(alert.description)
                if alert.recommendation:
                    st.caption(f"💡 {alert.recommendation}")
                if alert.raw_value is not None and alert.threshold_value is not None:
                    st.caption(
                        f"Valor detectado: {alert.raw_value:.1f} &nbsp;·&nbsp; "
                        f"Limiar: {alert.threshold_value:.1f}"
                    )

            with action_col:
                # Map link: pre-fill map filter to this alert's region
                if alert.biome_id or alert.region_id:
                    if st.button(
                        "🗺 Ver no mapa / View on map",
                        key=f"map_{alert.alert_id}",
                        use_container_width=True,
                    ):
                        # Pre-fill shared filter state so map page opens filtered
                        from src.ui.components.filters import FilterState
                        _fs = st.session_state.get("filter_state", FilterState())
                        if alert.biome_id and alert.biome_id not in _fs.biomes:
                            _fs.biomes = [alert.biome_id]
                        if alert.region_id and alert.region_id not in _fs.states:
                            _fs.states = [alert.region_id]
                        st.session_state["filter_state"] = _fs
                        st.switch_page("ui/pages/map_viewer.py")

                if alert.status == AlertStatus.ACTIVE:
                    if st.button(
                        "📁 Arquivar / Archive",
                        key=f"archive_{alert.alert_id}",
                        use_container_width=True,
                    ):
                        with get_db_session() as db:
                            from sqlalchemy import select
                            row = db.execute(
                                select(AlertDB).where(AlertDB.alert_id == alert.alert_id)
                            ).scalar_one_or_none()
                            if row:
                                row.status = AlertStatus.ARCHIVED
                                row.updated_at = datetime.utcnow()
                        st.rerun()

                    if st.button(
                        "✅ Resolver / Resolve",
                        key=f"resolve_{alert.alert_id}",
                        use_container_width=True,
                    ):
                        with get_db_session() as db:
                            from sqlalchemy import select
                            row = db.execute(
                                select(AlertDB).where(AlertDB.alert_id == alert.alert_id)
                            ).scalar_one_or_none()
                            if row:
                                row.status = AlertStatus.RESOLVED
                                row.updated_at = datetime.utcnow()
                        st.rerun()

                elif alert.status in (AlertStatus.ARCHIVED, AlertStatus.RESOLVED):
                    if st.button(
                        "↩ Reativar / Reactivate",
                        key=f"reactivate_{alert.alert_id}",
                        use_container_width=True,
                    ):
                        with get_db_session() as db:
                            from sqlalchemy import select
                            row = db.execute(
                                select(AlertDB).where(AlertDB.alert_id == alert.alert_id)
                            ).scalar_one_or_none()
                            if row:
                                row.status = AlertStatus.ACTIVE
                                row.updated_at = datetime.utcnow()
                        st.rerun()

# ------------------------------------------------------------------ #
# Footer                                                                #
# ------------------------------------------------------------------ #

st.divider()
st.caption(
    "Alertas gerados automaticamente a partir dos dados INPE (DETER e BDQueimadas). "
    "Limiares configurados em `settings.py`. "
    "/ Alerts auto-generated from INPE data (DETER and BDQueimadas). "
    "Thresholds configured in `settings.py`."
)
