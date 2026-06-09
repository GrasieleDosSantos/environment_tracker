"""Alert generator: evaluates INPE data against configured thresholds.

Fire outbreak:       fire hotspot count in the last 24 h exceeds alert_threshold_fires
                     (default 100 per region, configurable in settings.py)
Deforestation spike: deforestation area in the requested period exceeds
                     alert_threshold_deforestation % above the 12-month average
                     (default 50 %, configurable in settings.py)

Generated alerts are persisted to the ``alerts`` table so the Alerts page can
display, filter, and archive them independently of the live INPE fetch.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from src.config.constants import AlertSeverity, AlertStatus, AlertType, INPESource
from src.config.settings import get_settings
from src.database.connection import get_db_session
from src.database.models import AlertDB
from src.models.environmental import EnvironmentalAlert
from src.utils.logging import get_logger

_log = get_logger(__name__)


# ------------------------------------------------------------------ #
# Severity helpers                                                      #
# ------------------------------------------------------------------ #

def _fire_severity(count: int, threshold: int) -> AlertSeverity:
    ratio = count / max(threshold, 1)
    if ratio >= 10:
        return AlertSeverity.CRITICAL
    if ratio >= 5:
        return AlertSeverity.HIGH
    return AlertSeverity.MEDIUM


def _deforestation_severity(pct_above: float) -> AlertSeverity:
    if pct_above >= 150:
        return AlertSeverity.CRITICAL
    if pct_above >= 100:
        return AlertSeverity.HIGH
    return AlertSeverity.MEDIUM


# ------------------------------------------------------------------ #
# Core public functions                                                 #
# ------------------------------------------------------------------ #

def generate_alert(
    event_type: AlertType,
    severity: AlertSeverity,
    description: str,
    recommendation: str,
    region_id: str | None = None,
    biome_id: str | None = None,
    raw_value: float | None = None,
    threshold_value: float | None = None,
    affected_area_km2: float | None = None,
    data_source: INPESource = INPESource.FOGO,
) -> EnvironmentalAlert:
    """Construct an EnvironmentalAlert with a stable UUID."""
    return EnvironmentalAlert(
        alert_id=str(uuid.uuid4()),
        event_type=event_type,
        severity_level=severity,
        region_id=region_id,
        biome_id=biome_id,
        detection_date=datetime.now(tz=timezone.utc),
        description=description,
        recommendation=recommendation,
        affected_area_km2=affected_area_km2,
        raw_value=raw_value,
        threshold_value=threshold_value,
        data_source=data_source,
        status=AlertStatus.ACTIVE,
    )


def evaluate_alert_thresholds(
    fire_count_24h: int,
    deforestation_km2: float,
    avg_deforestation_km2: float | None,
    region_id: str | None = None,
    biome_id: str | None = None,
) -> list[EnvironmentalAlert]:
    """Evaluate snapshot values against configured thresholds.

    Returns a (possibly empty) list of new EnvironmentalAlert objects.
    Callers are responsible for persisting them via ``persist_alerts()``.
    """
    settings = get_settings()
    fire_threshold = settings.alert_threshold_fires
    deforest_pct_threshold = settings.alert_threshold_deforestation

    alerts: list[EnvironmentalAlert] = []

    # Fire outbreak check
    if fire_count_24h >= fire_threshold:
        severity = _fire_severity(fire_count_24h, fire_threshold)
        location = biome_id or region_id or "Brasil"
        alerts.append(generate_alert(
            event_type=AlertType.FIRE_OUTBREAK,
            severity=severity,
            description=(
                f"Surto de queimadas detectado: {fire_count_24h} focos nas últimas 24h "
                f"({location}). / Fire outbreak detected: {fire_count_24h} hotspots "
                f"in the last 24 h ({location})."
            ),
            recommendation=(
                "Monitore as áreas de risco e acione os órgãos responsáveis. "
                "/ Monitor risk areas and notify relevant authorities."
            ),
            region_id=region_id,
            biome_id=biome_id,
            raw_value=float(fire_count_24h),
            threshold_value=float(fire_threshold),
            data_source=INPESource.FOGO,
        ))

    # Deforestation spike check
    if (
        avg_deforestation_km2 is not None
        and avg_deforestation_km2 > 0
        and deforestation_km2 > 0
    ):
        pct_above = ((deforestation_km2 - avg_deforestation_km2) / avg_deforestation_km2) * 100
        if pct_above >= deforest_pct_threshold:
            severity = _deforestation_severity(pct_above)
            location = biome_id or region_id or "Brasil"
            alerts.append(generate_alert(
                event_type=AlertType.DEFORESTATION_SPIKE,
                severity=severity,
                description=(
                    f"Pico de desmatamento: {deforestation_km2:.1f} km² detectados em {location} "
                    f"({pct_above:.0f}% acima da média dos últimos 12 meses). "
                    f"/ Deforestation spike: {deforestation_km2:.1f} km² detected in {location} "
                    f"({pct_above:.0f}% above 12-month average)."
                ),
                recommendation=(
                    "Acione fiscalização em campo e verifique as imagens de satélite. "
                    "/ Trigger field inspection and verify satellite imagery."
                ),
                region_id=region_id,
                biome_id=biome_id,
                raw_value=round(deforestation_km2, 2),
                threshold_value=round(avg_deforestation_km2, 2),
                affected_area_km2=round(deforestation_km2, 2),
                data_source=INPESource.DETER,
            ))

    return alerts


def check_alert_escalation(
    existing: AlertDB,
    new_raw_value: float,
) -> bool:
    """Return True if *existing* alert should be escalated to a higher severity.

    Escalation triggers when the new raw value is at least 2× the value that
    originally triggered the alert.
    """
    if existing.raw_value is None or existing.raw_value <= 0:
        return False
    return new_raw_value >= existing.raw_value * 2


def persist_alerts(alerts: list[EnvironmentalAlert]) -> int:
    """Write new alerts to the database; skip duplicates (same type + region + day).

    Returns the number of alerts actually inserted.
    """
    if not alerts:
        return 0

    inserted = 0
    today_start = datetime.now(tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).replace(tzinfo=None)

    with get_db_session() as db:
        for alert in alerts:
            # Deduplicate: one alert per (event_type, region_id/biome_id) per calendar day
            from sqlalchemy import select, func
            existing = db.execute(
                select(AlertDB).where(
                    AlertDB.event_type == alert.event_type.value,
                    AlertDB.region_id == alert.region_id,
                    AlertDB.biome_id == alert.biome_id,
                    AlertDB.detection_date >= today_start,
                )
            ).scalar_one_or_none()

            if existing:
                # Escalate if warranted
                if alert.raw_value and check_alert_escalation(existing, alert.raw_value):
                    existing.severity_level = alert.severity_level.value
                    existing.raw_value = alert.raw_value
                    existing.description = alert.description
                    existing.updated_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
                    _log.info(
                        "alert_escalated",
                        alert_id=existing.alert_id,
                        new_severity=alert.severity_level.value,
                    )
            else:
                db.add(AlertDB(
                    alert_id=alert.alert_id,
                    event_type=alert.event_type.value,
                    severity_level=alert.severity_level.value,
                    region_id=alert.region_id,
                    biome_id=alert.biome_id,
                    detection_date=alert.detection_date.replace(tzinfo=None),
                    description=alert.description,
                    recommendation=alert.recommendation,
                    affected_area_km2=alert.affected_area_km2,
                    raw_value=alert.raw_value,
                    threshold_value=alert.threshold_value,
                    status=AlertStatus.ACTIVE.value,
                    data_source=alert.data_source.value,
                ))
                inserted += 1
                _log.info(
                    "alert_created",
                    event_type=alert.event_type.value,
                    severity=alert.severity_level.value,
                    region=alert.region_id,
                    biome=alert.biome_id,
                )

    return inserted


def run_alert_check(
    state: str | None = None,
    biome_id: str | None = None,
) -> list[EnvironmentalAlert]:
    """Fetch current INPE data, evaluate thresholds, persist new alerts.

    Returns the list of newly generated alerts (may be empty).
    """
    from src.services.inpe_integration.deter_client import fetch_deter_for_biomes, fetch_deter_time_series
    from src.services.inpe_integration.fogo_client import fetch_current_hotspots
    from src.utils.date_utils import today_brazil
    from datetime import date

    today = today_brazil()
    year_ago = today - timedelta(days=365)

    # Fire: last 48 h hotspots as a proxy for 24 h (WFS hourly resolution varies)
    try:
        hotspots_48h = fetch_current_hotspots(state=state, biome=biome_id)
        fire_count = len(hotspots_48h)
    except Exception as exc:
        _log.warning("alert_check_fogo_failed", error=str(exc))
        fire_count = 0

    # Deforestation: current period vs. 12-month average
    try:
        if biome_id:
            recent = fetch_deter_for_biomes(
                biome_ids=[biome_id], state=state,
                start=today - timedelta(days=30), end=today,
            )
            historical = fetch_deter_for_biomes(
                biome_ids=[biome_id], state=state,
                start=year_ago, end=today,
            )
        else:
            recent = fetch_deter_time_series(
                state=state, start=today - timedelta(days=30), end=today,
            )
            historical = fetch_deter_time_series(
                state=state, start=year_ago, end=today,
            )
        deforest_km2 = sum(a.area_km2 or 0.0 for a in recent)
        # Monthly average from the last 12 months
        months_with_data = 12
        avg_monthly = sum(a.area_km2 or 0.0 for a in historical) / months_with_data
    except Exception as exc:
        _log.warning("alert_check_deter_failed", error=str(exc))
        deforest_km2 = 0.0
        avg_monthly = None

    alerts = evaluate_alert_thresholds(
        fire_count_24h=fire_count,
        deforestation_km2=deforest_km2,
        avg_deforestation_km2=avg_monthly,
        region_id=state,
        biome_id=biome_id,
    )

    if alerts:
        inserted = persist_alerts(alerts)
        _log.info("alert_check_complete", generated=len(alerts), inserted=inserted)

    return alerts
