"""Unit tests for src/services/analysis/trend_analyzer.py."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.services.analysis.trend_analyzer import (
    TrendInfo,
    calculate_trend,
    compare_periods,
    prodes_annual_series,
    smoothed_series,
    trend_line_series,
)


# ------------------------------------------------------------------ #
# calculate_trend                                                        #
# ------------------------------------------------------------------ #

class TestCalculateTrend:
    def test_increasing_series(self, monthly_df_increasing):
        info = calculate_trend(monthly_df_increasing)
        assert info.direction == "increasing"
        assert info.slope_per_month > 0
        assert info.n_points == 24

    def test_decreasing_series(self, monthly_df_decreasing):
        info = calculate_trend(monthly_df_decreasing)
        assert info.direction == "decreasing"
        assert info.slope_per_month < 0

    def test_flat_series_is_stable(self, monthly_df_flat):
        info = calculate_trend(monthly_df_flat)
        assert info.direction == "stable"
        assert abs(info.slope) < 1e-6

    def test_empty_dataframe(self):
        info = calculate_trend(pd.DataFrame(columns=["month", "area_km2"]))
        assert info.direction == "stable"
        assert info.n_points == 0
        assert info.slope == 0.0

    def test_single_point(self):
        df = pd.DataFrame({"month": [date(2024, 1, 1)], "area_km2": [42.0]})
        info = calculate_trend(df)
        assert info.n_points == 1
        assert info.slope == 0.0

    def test_r_squared_bounds(self, monthly_df_increasing):
        info = calculate_trend(monthly_df_increasing)
        assert 0.0 <= info.r_squared <= 1.0

    def test_perfect_linear_fit(self):
        months = pd.date_range("2022-01-01", periods=12, freq="MS")
        df = pd.DataFrame({"month": months, "area_km2": [float(i * 10) for i in range(12)]})
        info = calculate_trend(df)
        assert info.r_squared > 0.99

    def test_pct_change_over_period(self, monthly_df_increasing):
        info = calculate_trend(monthly_df_increasing)
        # series goes 10 → 33, pct_change = (33-10)/10 * 100 = 230%
        assert abs(info.pct_change_over_period - 230.0) < 1.0

    def test_custom_columns(self):
        months = pd.date_range("2023-01-01", periods=6, freq="MS")
        df = pd.DataFrame({"date": months, "count": [10, 20, 30, 40, 50, 60]})
        info = calculate_trend(df, date_col="date", value_col="count")
        assert info.direction == "increasing"

    def test_missing_column_returns_empty(self):
        df = pd.DataFrame({"month": pd.date_range("2022-01-01", periods=5, freq="MS")})
        info = calculate_trend(df, value_col="area_km2")
        assert info.n_points == 0


# ------------------------------------------------------------------ #
# trend_line_series                                                      #
# ------------------------------------------------------------------ #

class TestTrendLineSeries:
    def test_returns_correct_columns(self, monthly_df_increasing):
        tl = trend_line_series(monthly_df_increasing)
        assert "month" in tl.columns
        assert "trend" in tl.columns

    def test_same_length_as_input(self, monthly_df_increasing):
        tl = trend_line_series(monthly_df_increasing)
        assert len(tl) == len(monthly_df_increasing)

    def test_empty_returns_empty(self):
        tl = trend_line_series(pd.DataFrame(columns=["month", "area_km2"]))
        assert tl.empty

    def test_single_point_returns_empty(self):
        df = pd.DataFrame({"month": [date(2024, 1, 1)], "area_km2": [10.0]})
        tl = trend_line_series(df)
        assert tl.empty

    def test_increasing_trend_values_monotone(self, monthly_df_increasing):
        tl = trend_line_series(monthly_df_increasing)
        assert tl["trend"].iloc[-1] > tl["trend"].iloc[0]


# ------------------------------------------------------------------ #
# smoothed_series                                                        #
# ------------------------------------------------------------------ #

class TestSmoothedSeries:
    def test_returns_correct_columns(self, monthly_df_increasing):
        sm = smoothed_series(monthly_df_increasing)
        assert "month" in sm.columns
        assert "smoothed" in sm.columns

    def test_same_length_as_input(self, monthly_df_increasing):
        sm = smoothed_series(monthly_df_increasing)
        assert len(sm) == len(monthly_df_increasing)

    def test_empty_returns_empty(self):
        sm = smoothed_series(pd.DataFrame(columns=["month", "area_km2"]))
        assert sm.empty

    def test_short_series_uses_rolling_fallback(self):
        months = pd.date_range("2024-01-01", periods=3, freq="MS")
        df = pd.DataFrame({"month": months, "area_km2": [10.0, 20.0, 30.0]})
        sm = smoothed_series(df, window=5)
        assert len(sm) == 3
        assert not sm["smoothed"].isna().all()


# ------------------------------------------------------------------ #
# compare_periods                                                        #
# ------------------------------------------------------------------ #

class TestComparePeriods:
    def test_basic_comparison(self, monthly_df_increasing):
        cmp = compare_periods(
            monthly_df_increasing,
            period_a=(date(2022, 1, 1), date(2022, 12, 31)),
            period_b=(date(2023, 1, 1), date(2023, 12, 31)),
        )
        assert cmp.mean_b > cmp.mean_a
        assert cmp.direction == "increasing"

    def test_decreasing_direction(self, monthly_df_decreasing):
        cmp = compare_periods(
            monthly_df_decreasing,
            period_a=(date(2022, 1, 1), date(2022, 12, 31)),
            period_b=(date(2023, 1, 1), date(2023, 12, 31)),
        )
        assert cmp.direction == "decreasing"

    def test_labels_preserved(self, monthly_df_increasing):
        cmp = compare_periods(
            monthly_df_increasing,
            period_a=(date(2022, 1, 1), date(2022, 6, 30)),
            period_b=(date(2022, 7, 1), date(2022, 12, 31)),
            label_a="First half",
            label_b="Second half",
        )
        assert cmp.label_a == "First half"
        assert cmp.label_b == "Second half"

    def test_empty_dataframe(self):
        cmp = compare_periods(
            pd.DataFrame(columns=["month", "area_km2"]),
            period_a=(date(2022, 1, 1), date(2022, 6, 30)),
            period_b=(date(2022, 7, 1), date(2022, 12, 31)),
        )
        assert cmp.mean_a == 0.0
        assert cmp.mean_b == 0.0
        assert cmp.p_value is None

    def test_pct_change_none_when_mean_a_zero(self):
        months = pd.date_range("2022-01-01", periods=6, freq="MS")
        df = pd.DataFrame({"month": months, "area_km2": [0, 0, 0, 10, 20, 30]})
        cmp = compare_periods(
            df,
            period_a=(date(2022, 1, 1), date(2022, 3, 31)),
            period_b=(date(2022, 4, 1), date(2022, 6, 30)),
        )
        assert cmp.pct_change is None

    def test_mann_whitney_computed_with_enough_points(self, monthly_df_increasing):
        cmp = compare_periods(
            monthly_df_increasing,
            period_a=(date(2022, 1, 1), date(2022, 12, 31)),
            period_b=(date(2023, 1, 1), date(2023, 12, 31)),
        )
        assert cmp.p_value is not None
        assert 0.0 <= cmp.p_value <= 1.0


# ------------------------------------------------------------------ #
# prodes_annual_series                                                   #
# ------------------------------------------------------------------ #

class TestProdesAnnualSeries:
    def test_returns_expected_columns(self, prodes_records):
        df = prodes_annual_series(prodes_records)
        assert "year_date" in df.columns
        assert "area_km2" in df.columns

    def test_sorted_by_year(self, prodes_records):
        df = prodes_annual_series(prodes_records)
        assert df["year_date"].is_monotonic_increasing

    def test_sums_area_per_year(self, prodes_records):
        # Add a second record for the same year/state
        extra = prodes_records[0].model_copy(update={"area_km2": 10.0})
        df = prodes_annual_series(prodes_records + [extra])
        first_year = df["year_date"].dt.year.min()
        base_area = next(r.area_km2 for r in prodes_records if r.year == first_year)
        row = df[df["year_date"].dt.year == first_year]
        assert abs(row["area_km2"].values[0] - (base_area + 10.0)) < 0.01

    def test_state_filter(self, prodes_records):
        df = prodes_annual_series(prodes_records, state="RS")
        assert len(df) == 6  # all 6 years pass (all are RS)

    def test_state_filter_excludes_others(self, prodes_records):
        df = prodes_annual_series(prodes_records, state="SP")
        assert df.empty

    def test_biome_filter(self, prodes_records):
        df = prodes_annual_series(prodes_records, biome="Pampa")
        assert len(df) == 6

    def test_empty_records(self):
        df = prodes_annual_series([])
        assert df.empty
        assert "year_date" in df.columns
