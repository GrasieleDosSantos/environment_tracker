"""Unit tests for src/services/analysis/alert_generator.py.

Tests cover all pure-logic functions: severity mapping, alert construction,
threshold evaluation, and escalation detection.  Database-dependent functions
(persist_alerts, run_alert_check) are covered in the integration suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config.constants import AlertSeverity, AlertStatus, AlertType, INPESource
from src.database.models import AlertDB
from src.services.analysis.alert_generator import (
    _deforestation_severity,
    _fire_severity,
    check_alert_escalation,
    evaluate_alert_thresholds,
    generate_alert,
)


# ------------------------------------------------------------------ #
# _fire_severity                                                        #
# ------------------------------------------------------------------ #

class TestFireSeverity:
    def test_just_at_threshold_is_medium(self):
        assert _fire_severity(100, 100) == AlertSeverity.MEDIUM

    def test_five_times_threshold_is_high(self):
        # ratio = 500/100 = 5.0 → HIGH
        assert _fire_severity(500, 100) == AlertSeverity.HIGH

    def test_ten_times_threshold_is_critical(self):
        # ratio = 1000/100 = 10.0 → CRITICAL
        assert _fire_severity(1000, 100) == AlertSeverity.CRITICAL

    def test_below_five_times_is_medium(self):
        # ratio = 499/100 = 4.99 → MEDIUM
        assert _fire_severity(499, 100) == AlertSeverity.MEDIUM

    def test_just_above_ten_is_critical(self):
        assert _fire_severity(1001, 100) == AlertSeverity.CRITICAL

    def test_custom_threshold_scales_correctly(self):
        # threshold=50, count=500 → ratio=10 → CRITICAL
        assert _fire_severity(500, 50) == AlertSeverity.CRITICAL


# ------------------------------------------------------------------ #
# _deforestation_severity                                               #
# ------------------------------------------------------------------ #

class TestDeforestationSeverity:
    def test_50_pct_above_is_medium(self):
        assert _deforestation_severity(50.0) == AlertSeverity.MEDIUM

    def test_99_pct_above_is_medium(self):
        assert _deforestation_severity(99.9) == AlertSeverity.MEDIUM

    def test_100_pct_above_is_high(self):
        assert _deforestation_severity(100.0) == AlertSeverity.HIGH

    def test_149_pct_above_is_high(self):
        assert _deforestation_severity(149.9) == AlertSeverity.HIGH

    def test_150_pct_above_is_critical(self):
        assert _deforestation_severity(150.0) == AlertSeverity.CRITICAL

    def test_very_large_pct_is_critical(self):
        assert _deforestation_severity(999.0) == AlertSeverity.CRITICAL


# ------------------------------------------------------------------ #
# generate_alert                                                        #
# ------------------------------------------------------------------ #

class TestGenerateAlert:
    def test_returns_environmental_alert(self):
        from src.models.environmental import EnvironmentalAlert
        alert = generate_alert(
            event_type=AlertType.FIRE_OUTBREAK,
            severity=AlertSeverity.HIGH,
            description="Test fire",
            recommendation="Test rec",
        )
        assert isinstance(alert, EnvironmentalAlert)

    def test_alert_id_is_uuid_string(self):
        import uuid
        alert = generate_alert(
            event_type=AlertType.FIRE_OUTBREAK,
            severity=AlertSeverity.MEDIUM,
            description="d",
            recommendation="r",
        )
        # Should not raise
        uuid.UUID(alert.alert_id)

    def test_status_is_active(self):
        alert = generate_alert(
            event_type=AlertType.DEFORESTATION_SPIKE,
            severity=AlertSeverity.HIGH,
            description="d",
            recommendation="r",
        )
        assert alert.status == AlertStatus.ACTIVE

    def test_optional_fields_propagated(self):
        alert = generate_alert(
            event_type=AlertType.FIRE_OUTBREAK,
            severity=AlertSeverity.CRITICAL,
            description="d",
            recommendation="r",
            region_id="PA",
            biome_id="amazonia",
            raw_value=1500.0,
            threshold_value=100.0,
            affected_area_km2=250.0,
            data_source=INPESource.DETER,
        )
        assert alert.region_id == "PA"
        assert alert.biome_id == "amazonia"
        assert alert.raw_value == pytest.approx(1500.0)
        assert alert.threshold_value == pytest.approx(100.0)
        assert alert.affected_area_km2 == pytest.approx(250.0)
        assert alert.data_source == INPESource.DETER

    def test_detection_date_is_utc_aware(self):
        alert = generate_alert(
            event_type=AlertType.FIRE_OUTBREAK,
            severity=AlertSeverity.MEDIUM,
            description="d",
            recommendation="r",
        )
        assert alert.detection_date.tzinfo is not None


# ------------------------------------------------------------------ #
# evaluate_alert_thresholds                                             #
# ------------------------------------------------------------------ #

class TestEvaluateAlertThresholds:
    """Uses default settings thresholds: fire=100, deforest=50%."""

    def test_no_alerts_when_below_thresholds(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=50,
            deforestation_km2=10.0,
            avg_deforestation_km2=100.0,  # 10 is 90% BELOW average — no spike
        )
        assert alerts == []

    def test_fire_alert_at_threshold(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=100,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
        )
        assert len(alerts) == 1
        assert alerts[0].event_type == AlertType.FIRE_OUTBREAK

    def test_fire_alert_has_correct_severity(self):
        # 1000 hotspots at threshold=100 → ratio=10 → CRITICAL
        alerts = evaluate_alert_thresholds(
            fire_count_24h=1000,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
        )
        assert alerts[0].severity_level == AlertSeverity.CRITICAL

    def test_fire_alert_raw_value_matches_count(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=250,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
        )
        assert alerts[0].raw_value == pytest.approx(250.0)
        assert alerts[0].data_source == INPESource.FOGO

    def test_deforestation_spike_alert(self):
        # avg=100, current=160 → 60% above avg (>50%) → alert
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=160.0,
            avg_deforestation_km2=100.0,
        )
        assert len(alerts) == 1
        assert alerts[0].event_type == AlertType.DEFORESTATION_SPIKE

    def test_deforestation_spike_affected_area_set(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=160.0,
            avg_deforestation_km2=100.0,
        )
        assert alerts[0].affected_area_km2 == pytest.approx(160.0)
        assert alerts[0].data_source == INPESource.DETER

    def test_deforestation_no_alert_below_threshold(self):
        # avg=100, current=149 → 49% above → below 50% threshold
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=149.0,
            avg_deforestation_km2=100.0,
        )
        assert alerts == []

    def test_deforestation_skipped_when_avg_is_none(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=500.0,
            avg_deforestation_km2=None,
        )
        assert alerts == []

    def test_deforestation_skipped_when_avg_is_zero(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=500.0,
            avg_deforestation_km2=0.0,
        )
        assert alerts == []

    def test_deforestation_skipped_when_current_is_zero(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=0,
            deforestation_km2=0.0,
            avg_deforestation_km2=100.0,
        )
        assert alerts == []

    def test_both_thresholds_exceeded_returns_two_alerts(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=500,
            deforestation_km2=200.0,
            avg_deforestation_km2=100.0,  # 100% above avg
        )
        types = {a.event_type for a in alerts}
        assert AlertType.FIRE_OUTBREAK in types
        assert AlertType.DEFORESTATION_SPIKE in types

    def test_region_and_biome_propagated_to_alerts(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=200,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
            region_id="MT",
            biome_id="cerrado",
        )
        assert alerts[0].region_id == "MT"
        assert alerts[0].biome_id == "cerrado"

    def test_fire_alert_below_threshold_no_alert(self):
        alerts = evaluate_alert_thresholds(
            fire_count_24h=99,
            deforestation_km2=0.0,
            avg_deforestation_km2=None,
        )
        assert alerts == []


# ------------------------------------------------------------------ #
# check_alert_escalation                                                #
# ------------------------------------------------------------------ #

class TestCheckAlertEscalation:
    def _make_db_alert(self, raw_value: float | None) -> AlertDB:
        row = MagicMock(spec=AlertDB)
        row.raw_value = raw_value
        return row

    def test_escalates_when_new_is_double(self):
        row = self._make_db_alert(100.0)
        assert check_alert_escalation(row, 200.0) is True

    def test_escalates_when_new_exceeds_double(self):
        row = self._make_db_alert(100.0)
        assert check_alert_escalation(row, 250.0) is True

    def test_no_escalation_just_below_double(self):
        row = self._make_db_alert(100.0)
        assert check_alert_escalation(row, 199.9) is False

    def test_no_escalation_when_raw_value_none(self):
        row = self._make_db_alert(None)
        assert check_alert_escalation(row, 500.0) is False

    def test_no_escalation_when_raw_value_zero(self):
        row = self._make_db_alert(0.0)
        assert check_alert_escalation(row, 500.0) is False

    def test_exact_double_triggers_escalation(self):
        row = self._make_db_alert(50.0)
        assert check_alert_escalation(row, 100.0) is True
