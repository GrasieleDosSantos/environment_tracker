"""Unit tests for src/services/analysis/aggregator.py."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.services.analysis.aggregator import (
    aggregate_multi_source,
    deter_to_monthly_df,
    deter_to_state_df,
    fogo_to_daily_df,
)
from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot


# ------------------------------------------------------------------ #
# deter_to_monthly_df                                                   #
# ------------------------------------------------------------------ #

class TestDeterToMonthlyDf:
    def test_empty_returns_empty_df(self):
        df = deter_to_monthly_df([])
        assert df.empty
        assert "month" in df.columns

    def test_groups_by_month(self, deter_alerts):
        df = deter_to_monthly_df(deter_alerts)
        # 12 months → 12 rows
        assert len(df) == 12

    def test_sums_area_per_month(self, deter_alerts):
        df = deter_to_monthly_df(deter_alerts)
        # Each month has PA(50) + MT(30) = 80 km²
        assert df["area_km2"].values == pytest.approx([80.0] * 12)

    def test_alert_without_date_excluded(self):
        alerts = [DETERAlert(view_date=None, area_km2=10.0, state="AM")]
        df = deter_to_monthly_df(alerts)
        assert df.empty

    def test_month_column_is_datetime(self, deter_alerts):
        df = deter_to_monthly_df(deter_alerts)
        import pandas as pd
        assert pd.api.types.is_datetime64_any_dtype(df["month"])

    def test_sorted_ascending(self, deter_alerts):
        df = deter_to_monthly_df(deter_alerts)
        assert df["month"].is_monotonic_increasing


# ------------------------------------------------------------------ #
# deter_to_state_df                                                     #
# ------------------------------------------------------------------ #

class TestDeterToStateDf:
    def test_empty_returns_empty_df(self):
        df = deter_to_state_df([])
        assert df.empty

    def test_groups_by_state(self, deter_alerts):
        df = deter_to_state_df(deter_alerts)
        assert set(df["state"].tolist()) == {"PA", "MT"}

    def test_sums_area_per_state(self, deter_alerts):
        df = deter_to_state_df(deter_alerts)
        pa_row = df[df["state"] == "PA"]
        # PA: 50 km² × 12 months = 600 km²
        assert pa_row["area_km2"].values[0] == pytest.approx(600.0)

    def test_sorted_by_area_descending(self, deter_alerts):
        df = deter_to_state_df(deter_alerts)
        assert df["area_km2"].is_monotonic_decreasing


# ------------------------------------------------------------------ #
# fogo_to_daily_df                                                      #
# ------------------------------------------------------------------ #

class TestFogoToDailyDf:
    def test_empty_returns_empty_df(self):
        df = fogo_to_daily_df([])
        assert df.empty

    def test_groups_by_date(self, fire_hotspots):
        df = fogo_to_daily_df(fire_hotspots)
        # All hotspots share the same detection date
        assert len(df) == 1
        assert df["count"].values[0] == 30

    def test_hotspot_without_date_excluded(self):
        h = FireHotspot(latitude=-10.0, longitude=-55.0)
        df = fogo_to_daily_df([h])
        assert df.empty


# ------------------------------------------------------------------ #
# aggregate_multi_source                                                #
# ------------------------------------------------------------------ #

class TestAggregateMultiSource:
    def test_basic_aggregation(self, deter_alerts, fire_hotspots):
        snap = aggregate_multi_source(
            deter_alerts=deter_alerts,
            fogo_hotspots_48h=fire_hotspots,
            fogo_hotspots_period=fire_hotspots,
            region_label="Amazônia",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        assert snap.deforestation_km2 == pytest.approx(960.0)  # 80 × 12
        assert snap.fire_count_48h == 30
        assert snap.region_label == "Amazônia"

    def test_empty_inputs(self):
        snap = aggregate_multi_source(
            deter_alerts=[],
            fogo_hotspots_48h=[],
            fogo_hotspots_period=[],
            region_label="Brasil",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        assert snap.deforestation_km2 == 0.0
        assert snap.fire_count_48h == 0

    def test_fire_risk_level_critical(self, fire_hotspots):
        # Create 1001 hotspots to trigger critical
        hotspots = fire_hotspots * 34  # 30 * 34 = 1020
        snap = aggregate_multi_source(
            deter_alerts=[],
            fogo_hotspots_48h=hotspots,
            fogo_hotspots_period=hotspots,
            region_label="Brasil",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        assert snap.fire_risk_level == "critical"

    def test_fetched_at_is_recent(self, deter_alerts, fire_hotspots):
        snap = aggregate_multi_source(
            deter_alerts=deter_alerts,
            fogo_hotspots_48h=fire_hotspots,
            fogo_hotspots_period=fire_hotspots,
            region_label="Brasil",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        age = (datetime.now(timezone.utc) - snap.fetched_at).total_seconds()
        assert age < 5  # created within the test run
