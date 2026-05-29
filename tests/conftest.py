"""Shared pytest fixtures for all test suites."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot
from src.services.inpe_integration.prodes_client import PRODESData


# ------------------------------------------------------------------ #
# DETER fixtures                                                        #
# ------------------------------------------------------------------ #

@pytest.fixture
def deter_alerts() -> list[DETERAlert]:
    """12 months of synthetic DETER alerts spread across two states."""
    alerts = []
    for month in range(1, 13):
        for state, area in [("PA", 50.0), ("MT", 30.0)]:
            alerts.append(DETERAlert(
                view_date=date(2024, month, 15),
                classname="DESMATAMENTO_VEG",
                state=state,
                area_km2=area,
                biome="Amazônia",
            ))
    return alerts


@pytest.fixture
def single_deter_alert() -> DETERAlert:
    return DETERAlert(
        view_date=date(2024, 6, 1),
        classname="DESMATAMENTO_VEG",
        state="AM",
        area_km2=12.5,
        biome="Amazônia",
    )


# ------------------------------------------------------------------ #
# Fire hotspot fixtures                                                 #
# ------------------------------------------------------------------ #

@pytest.fixture
def fire_hotspots() -> list[FireHotspot]:
    """30 synthetic fire hotspots across two states."""
    hotspots = []
    for i in range(30):
        state = "MT" if i % 2 == 0 else "PA"
        hotspots.append(FireHotspot(
            latitude=-10.0 - i * 0.1,
            longitude=-55.0 + i * 0.05,
            state=state,
            biome="Cerrado" if state == "MT" else "Amazônia",
            detection_time=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        ))
    return hotspots


# ------------------------------------------------------------------ #
# PRODES fixtures                                                       #
# ------------------------------------------------------------------ #

@pytest.fixture
def prodes_records() -> list[PRODESData]:
    """Annual PRODES records for Pampa 2019–2024."""
    areas = {2019: 60.3, 2020: 51.1, 2021: 38.1, 2022: 28.8, 2023: 15.2, 2024: 9.9}
    return [
        PRODESData(year=yr, state="RS", biome="Pampa", area_km2=area)
        for yr, area in areas.items()
    ]


# ------------------------------------------------------------------ #
# DataFrame fixtures                                                    #
# ------------------------------------------------------------------ #

@pytest.fixture
def monthly_df_increasing() -> pd.DataFrame:
    """Monotonically increasing monthly series (24 months)."""
    months = pd.date_range("2022-01-01", periods=24, freq="MS")
    return pd.DataFrame({"month": months, "area_km2": range(10, 34)})


@pytest.fixture
def monthly_df_decreasing() -> pd.DataFrame:
    months = pd.date_range("2022-01-01", periods=24, freq="MS")
    return pd.DataFrame({"month": months, "area_km2": range(33, 9, -1)})


@pytest.fixture
def monthly_df_flat() -> pd.DataFrame:
    months = pd.date_range("2022-01-01", periods=24, freq="MS")
    return pd.DataFrame({"month": months, "area_km2": [100.0] * 24})
