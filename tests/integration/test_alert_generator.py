"""Integration tests for alert_generator.persist_alerts() against a real SQLite DB.

Each test gets an isolated temp database via the same fixture pattern used in
test_cache_manager.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config.constants import AlertSeverity, AlertStatus, AlertType, INPESource
from src.services.analysis.alert_generator import (
    evaluate_alert_thresholds,
    generate_alert,
    persist_alerts,
)


# ------------------------------------------------------------------ #
# Isolated DB fixture (same pattern as test_cache_manager.py)          #
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_alerts.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import src.config.settings as _settings_mod
    _settings_mod._settings = None

    import src.database.connection as _conn_mod
    _conn_mod._engine = None
    _conn_mod._SessionLocal = None

    import src.services.inpe_integration.cache_manager as _cache_mod
    _cache_mod._instance = None

    from src.database.connection import get_engine
    from src.database.models import Base
    Base.metadata.create_all(get_engine())

    yield

    _settings_mod._settings = None
    _conn_mod._engine = None
    _conn_mod._SessionLocal = None
    _cache_mod._instance = None


def _make_fire_alert(**kwargs) -> object:
    defaults = dict(
        event_type=AlertType.FIRE_OUTBREAK,
        severity=AlertSeverity.HIGH,
        description="Test fire outbreak",
        recommendation="Monitor risk areas.",
        region_id="PA",
        biome_id="amazonia",
        raw_value=500.0,
        threshold_value=100.0,
        data_source=INPESource.FOGO,
    )
    defaults.update(kwargs)
    return generate_alert(**defaults)


def _make_deforest_alert(**kwargs) -> object:
    defaults = dict(
        event_type=AlertType.DEFORESTATION_SPIKE,
        severity=AlertSeverity.MEDIUM,
        description="Test deforestation spike",
        recommendation="Trigger field inspection.",
        region_id="MT",
        biome_id="cerrado",
        raw_value=160.0,
        threshold_value=100.0,
        affected_area_km2=160.0,
        data_source=INPESource.DETER,
    )
    defaults.update(kwargs)
    return generate_alert(**defaults)


def _count_alerts_in_db() -> int:
    from sqlalchemy import select, func
    from src.database.connection import get_db_session
    from src.database.models import AlertDB
    with get_db_session() as db:
        return db.execute(select(func.count()).select_from(AlertDB)).scalar_one()


def _fetch_all_alerts() -> list:
    from sqlalchemy import select
    from src.database.connection import get_db_session
    from src.database.models import AlertDB
    with get_db_session() as db:
        return list(db.execute(select(AlertDB)).scalars().all())


# ------------------------------------------------------------------ #
# persist_alerts: basic insertion                                        #
# ------------------------------------------------------------------ #

class TestPersistAlertsInsertion:
    def test_empty_list_returns_zero(self):
        assert persist_alerts([]) == 0

    def test_single_alert_inserted(self):
        alert = _make_fire_alert()
        inserted = persist_alerts([alert])
        assert inserted == 1
        assert _count_alerts_in_db() == 1

    def test_multiple_alerts_inserted(self):
        alerts = [_make_fire_alert(), _make_deforest_alert()]
        inserted = persist_alerts(alerts)
        assert inserted == 2
        assert _count_alerts_in_db() == 2

    def test_persisted_fields_match_alert(self):
        alert = _make_fire_alert(region_id="AM", raw_value=750.0)
        persist_alerts([alert])
        rows = _fetch_all_alerts()
        assert len(rows) == 1
        row = rows[0]
        assert row.alert_id == alert.alert_id
        assert row.event_type == AlertType.FIRE_OUTBREAK
        assert row.severity_level == AlertSeverity.HIGH
        assert row.region_id == "AM"
        assert row.raw_value == pytest.approx(750.0)
        assert row.status == AlertStatus.ACTIVE

    def test_status_defaults_to_active(self):
        persist_alerts([_make_fire_alert()])
        rows = _fetch_all_alerts()
        assert rows[0].status == AlertStatus.ACTIVE


# ------------------------------------------------------------------ #
# persist_alerts: deduplication                                          #
# ------------------------------------------------------------------ #

class TestPersistAlertsDeduplication:
    def test_duplicate_same_day_not_reinserted(self):
        alert = _make_fire_alert()
        persist_alerts([alert])
        # Second call with a new alert of the same type/region/biome today
        alert2 = _make_fire_alert()
        inserted = persist_alerts([alert2])
        assert inserted == 0
        assert _count_alerts_in_db() == 1

    def test_different_type_same_region_both_inserted(self):
        fire = _make_fire_alert(region_id="PA", biome_id="amazonia")
        deforest = _make_deforest_alert(region_id="PA", biome_id="amazonia")
        inserted = persist_alerts([fire, deforest])
        assert inserted == 2

    def test_same_type_different_region_both_inserted(self):
        alert_pa = _make_fire_alert(region_id="PA", biome_id="amazonia")
        alert_mt = _make_fire_alert(region_id="MT", biome_id="cerrado")
        inserted = persist_alerts([alert_pa, alert_mt])
        assert inserted == 2


# ------------------------------------------------------------------ #
# persist_alerts: escalation                                            #
# ------------------------------------------------------------------ #

class TestPersistAlertsEscalation:
    def test_escalation_updates_severity_not_row_count(self):
        # Insert initial alert at HIGH
        alert1 = _make_fire_alert(raw_value=500.0, severity=AlertSeverity.HIGH)
        persist_alerts([alert1])
        assert _count_alerts_in_db() == 1

        # Second call with raw_value ≥ 2× → escalate
        alert2 = _make_fire_alert(
            raw_value=1000.0,
            severity=AlertSeverity.CRITICAL,
        )
        inserted = persist_alerts([alert2])

        # No new row inserted
        assert inserted == 0
        assert _count_alerts_in_db() == 1

        # Severity was upgraded
        rows = _fetch_all_alerts()
        assert rows[0].severity_level == AlertSeverity.CRITICAL
        assert rows[0].raw_value == pytest.approx(1000.0)

    def test_no_escalation_below_double(self):
        alert1 = _make_fire_alert(raw_value=500.0, severity=AlertSeverity.HIGH)
        persist_alerts([alert1])

        # raw_value = 999 < 500*2 → no escalation
        alert2 = _make_fire_alert(raw_value=999.0, severity=AlertSeverity.CRITICAL)
        persist_alerts([alert2])

        rows = _fetch_all_alerts()
        # Severity must remain HIGH
        assert rows[0].severity_level == AlertSeverity.HIGH


# ------------------------------------------------------------------ #
# evaluate_alert_thresholds → persist_alerts end-to-end                #
# ------------------------------------------------------------------ #

class TestEndToEndEvaluateAndPersist:
    def test_fire_threshold_exceeded_creates_db_row(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=200,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
            region_id="RO",
            biome_id="amazonia",
        )
        persist_alerts(alerts)
        rows = _fetch_all_alerts()
        assert len(rows) == 1
        assert rows[0].event_type == AlertType.FIRE_OUTBREAK
        assert rows[0].region_id == "RO"

    def test_both_thresholds_creates_two_rows(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=500,
            deforestation_km2=200.0,
            avg_deforestation_km2=100.0,
            region_id="MT",
            biome_id="cerrado",
        )
        persist_alerts(alerts)
        assert _count_alerts_in_db() == 2

    def test_below_thresholds_creates_no_rows(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=50,
            deforestation_km2=10.0,
            avg_deforestation_km2=100.0,
        )
        persist_alerts(alerts)
        assert _count_alerts_in_db() == 0
