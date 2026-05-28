"""Trend analysis utilities for environmental time-series data.

All functions accept pandas DataFrames produced by the aggregator helpers
(``deter_to_monthly_df``, ``fogo_to_daily_df``, etc.) and return plain
Python dataclasses so callers have no dependency on this module's internals.

Statistical backend: scipy (linregress, seasonal_decompose).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import savgol_filter
from scipy.stats import linregress


# ------------------------------------------------------------------ #
# Result types                                                          #
# ------------------------------------------------------------------ #

Direction = Literal["increasing", "decreasing", "stable"]


@dataclass
class TrendInfo:
    """Result of a linear trend calculation on a single time-series."""

    direction: Direction
    slope: float              # units per day
    slope_per_month: float    # units per 30 days (more readable)
    r_squared: float          # goodness-of-fit 0–1
    confidence: float         # same as r_squared, aliased for readability
    p_value: float            # significance of the slope (two-tailed t-test)
    n_points: int
    mean_value: float
    pct_change_over_period: float   # (last - first) / |first| * 100


@dataclass
class SeasonalComponents:
    """Additive seasonal decomposition: trend + seasonal + residual."""

    trend: pd.Series
    seasonal: pd.Series
    residual: pd.Series
    period_col: str
    value_col: str


@dataclass
class PeriodComparison:
    """Side-by-side comparison of two time periods."""

    label_a: str
    label_b: str
    mean_a: float
    mean_b: float
    total_a: float
    total_b: float
    absolute_change: float
    pct_change: float | None  # None when mean_a == 0
    direction: Direction
    p_value: float | None     # Mann-Whitney U test p-value; None if < 3 points each


# ------------------------------------------------------------------ #
# Linear trend                                                          #
# ------------------------------------------------------------------ #

_STABLE_THRESHOLD_FRACTION = 0.02  # < 2% of mean per month → "stable"


def calculate_trend(
    df: pd.DataFrame,
    date_col: str = "month",
    value_col: str = "area_km2",
) -> TrendInfo:
    """Fit a linear trend to *value_col* over time using scipy linregress.

    The date column is converted to a numeric ordinal (days since epoch)
    so the slope is in *units per day*; ``slope_per_month`` is slope × 30.
    Direction is determined by comparing the monthly slope to 2 % of the mean
    — small fluctuations are classified as "stable".

    Returns a :class:`TrendInfo` even for empty or single-point series;
    those edge cases carry zero slope and ``r_squared=0``.
    """
    if df.empty or value_col not in df.columns or date_col not in df.columns:
        return _empty_trend()

    series = df[[date_col, value_col]].dropna().sort_values(date_col)
    if len(series) < 2:
        v = float(series[value_col].iloc[0]) if len(series) == 1 else 0.0
        return TrendInfo(
            direction="stable", slope=0.0, slope_per_month=0.0,
            r_squared=0.0, confidence=0.0, p_value=1.0,
            n_points=len(series), mean_value=v, pct_change_over_period=0.0,
        )

    x = pd.to_datetime(series[date_col]).map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    y = series[value_col].to_numpy(dtype=float)

    result = linregress(x, y)
    slope = float(result.slope)
    slope_per_month = slope * 30.0
    r_squared = max(0.0, min(1.0, float(result.rvalue ** 2)))
    p_value = float(result.pvalue)

    mean_val = float(y.mean())
    stable_threshold = abs(mean_val) * _STABLE_THRESHOLD_FRACTION

    if abs(slope_per_month) < stable_threshold:
        direction: Direction = "stable"
    elif slope_per_month > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    first_val, last_val = float(y[0]), float(y[-1])
    pct_change = (last_val - first_val) / abs(first_val) * 100 if first_val != 0 else 0.0

    return TrendInfo(
        direction=direction,
        slope=slope,
        slope_per_month=slope_per_month,
        r_squared=r_squared,
        confidence=r_squared,
        p_value=p_value,
        n_points=len(series),
        mean_value=mean_val,
        pct_change_over_period=pct_change,
    )


def _empty_trend() -> TrendInfo:
    return TrendInfo(
        direction="stable", slope=0.0, slope_per_month=0.0,
        r_squared=0.0, confidence=0.0, p_value=1.0,
        n_points=0, mean_value=0.0, pct_change_over_period=0.0,
    )


# ------------------------------------------------------------------ #
# Trend line for chart overlay                                          #
# ------------------------------------------------------------------ #

def trend_line_series(
    df: pd.DataFrame,
    date_col: str = "month",
    value_col: str = "area_km2",
) -> pd.DataFrame:
    """Return a DataFrame with fitted linear trend values for chart overlay.

    Columns: [date_col, "trend"].  Empty when input is empty.
    """
    if df.empty or len(df) < 2:
        return pd.DataFrame(columns=[date_col, "trend"])

    series = df[[date_col, value_col]].dropna().sort_values(date_col)
    x = pd.to_datetime(series[date_col]).map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    y = series[value_col].to_numpy(dtype=float)

    result = linregress(x, y)
    trend_vals = result.slope * x + result.intercept

    out = series[[date_col]].copy()
    out["trend"] = trend_vals
    return out


def smoothed_series(
    df: pd.DataFrame,
    date_col: str = "month",
    value_col: str = "area_km2",
    window: int = 5,
) -> pd.DataFrame:
    """Return a Savitzky-Golay smoothed version of the series for chart overlay.

    Falls back to a centred rolling mean when there are fewer than *window*
    points (Savitzky-Golay requires at least *window* data points).
    Columns: [date_col, "smoothed"].
    """
    if df.empty:
        return pd.DataFrame(columns=[date_col, "smoothed"])

    series = df[[date_col, value_col]].dropna().sort_values(date_col).copy()
    y = series[value_col].to_numpy(dtype=float)

    if len(y) >= window and window >= 3:
        # window must be odd for savgol
        w = window if window % 2 == 1 else window + 1
        polyorder = min(2, w - 1)
        smoothed = savgol_filter(y, window_length=w, polyorder=polyorder)
    else:
        smoothed = (
            pd.Series(y)
            .rolling(window=max(2, window // 2), center=True, min_periods=1)
            .mean()
            .to_numpy()
        )

    out = series[[date_col]].copy()
    out["smoothed"] = smoothed
    return out


# ------------------------------------------------------------------ #
# Seasonal decomposition                                                #
# ------------------------------------------------------------------ #

def seasonal_decomposition(
    df: pd.DataFrame,
    date_col: str = "month",
    value_col: str = "area_km2",
    period: int = 12,
) -> SeasonalComponents:
    """Additive seasonal decomposition using statsmodels seasonal_decompose.

    Falls back to a centred rolling-mean trend + monthly-average seasonal
    component when statsmodels is unavailable or the series is too short.

    Requires at least 2 × *period* data points for a meaningful result.
    """
    if df.empty or len(df) < 2 * period:
        empty = pd.Series(dtype=float)
        return SeasonalComponents(
            trend=empty, seasonal=empty, residual=empty,
            period_col=date_col, value_col=value_col,
        )

    series = df[[date_col, value_col]].dropna().sort_values(date_col).copy()
    series[date_col] = pd.to_datetime(series[date_col])
    s = series.set_index(date_col)[value_col].asfreq("MS")   # monthly start

    try:
        from statsmodels.tsa.seasonal import seasonal_decompose as sm_decompose
        result = sm_decompose(s.dropna(), model="additive", period=period, extrapolate_trend="freq")
        return SeasonalComponents(
            trend=result.trend,
            seasonal=result.seasonal,
            residual=result.resid,
            period_col=date_col,
            value_col=value_col,
        )
    except Exception:
        # Manual fallback: rolling mean trend + monthly-average seasonal
        trend = s.rolling(window=period, center=True, min_periods=period // 2).mean()
        detrended = s - trend
        month_avg = detrended.groupby(detrended.index.month).mean()
        seasonal = pd.Series(
            [month_avg.get(d.month, 0.0) for d in detrended.index],
            index=detrended.index,
        )
        residual = s - trend - seasonal
        return SeasonalComponents(
            trend=trend, seasonal=seasonal, residual=residual,
            period_col=date_col, value_col=value_col,
        )


# ------------------------------------------------------------------ #
# Period comparison                                                      #
# ------------------------------------------------------------------ #

def compare_periods(
    df: pd.DataFrame,
    period_a: tuple[date, date],
    period_b: tuple[date, date],
    date_col: str = "month",
    value_col: str = "area_km2",
    label_a: str = "Período A",
    label_b: str = "Período B",
) -> PeriodComparison:
    """Compare aggregate statistics between two date ranges.

    Both tuples are inclusive ``(start, end)`` boundaries.
    A Mann-Whitney U test is run when both slices have ≥ 3 points.
    """
    col = pd.to_datetime(df[date_col]) if not df.empty else pd.Series(dtype="datetime64[ns]")

    def _slice(start: date, end: date) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)
        mask = (col >= pd.Timestamp(start)) & (col <= pd.Timestamp(end))
        return df.loc[mask, value_col].dropna()

    s_a = _slice(*period_a)
    s_b = _slice(*period_b)

    mean_a = float(s_a.mean()) if not s_a.empty else 0.0
    mean_b = float(s_b.mean()) if not s_b.empty else 0.0
    total_a = float(s_a.sum()) if not s_a.empty else 0.0
    total_b = float(s_b.sum()) if not s_b.empty else 0.0
    absolute_change = mean_b - mean_a
    pct_change = (absolute_change / abs(mean_a) * 100) if mean_a != 0 else None

    p_value: float | None = None
    if len(s_a) >= 3 and len(s_b) >= 3:
        try:
            _, p_value = stats.mannwhitneyu(s_a, s_b, alternative="two-sided")
            p_value = float(p_value)
        except Exception:
            pass

    if pct_change is None or abs(pct_change) < 2:
        direction: Direction = "stable"
    elif absolute_change > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return PeriodComparison(
        label_a=label_a,
        label_b=label_b,
        mean_a=mean_a,
        mean_b=mean_b,
        total_a=total_a,
        total_b=total_b,
        absolute_change=absolute_change,
        pct_change=pct_change,
        direction=direction,
        p_value=p_value,
    )


# ------------------------------------------------------------------ #
# Convenience builders from raw INPE records                            #
# ------------------------------------------------------------------ #

def fire_monthly_series(
    hotspots: list,
    state: str | None = None,
    biome: str | None = None,
) -> pd.DataFrame:
    """Convert FireHotspot records to a monthly count DataFrame ``[month, count]``."""
    from src.services.analysis.aggregator import fogo_to_daily_df

    if state:
        hotspots = [h for h in hotspots if h.state == state]
    if biome:
        hotspots = [h for h in hotspots if (h.biome or "").lower() == biome.lower()]

    daily = fogo_to_daily_df(hotspots)
    if daily.empty:
        return pd.DataFrame(columns=["month", "count"])

    daily["month"] = daily["date"].dt.to_period("M").dt.to_timestamp()
    return (
        daily.groupby("month")["count"]
        .sum()
        .reset_index()
    )


def deforestation_monthly_series(
    alerts: list,
    state: str | None = None,
    biome: str | None = None,
) -> pd.DataFrame:
    """Convert DETERAlert records to a monthly area DataFrame ``[month, area_km2, count]``."""
    from src.services.analysis.aggregator import deter_to_monthly_df

    if state:
        alerts = [a for a in alerts if a.state == state]
    if biome:
        alerts = [a for a in alerts if (a.biome or "").lower() == biome.lower()]

    return deter_to_monthly_df(alerts)
