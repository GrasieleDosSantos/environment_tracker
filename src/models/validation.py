from datetime import date
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from src.config.constants import BIOME_IDS, BRAZIL_BOUNDS, STATE_CODES


def validate_brazil_latitude(v: float) -> float:
    if not (BRAZIL_BOUNDS["min_lat"] <= v <= BRAZIL_BOUNDS["max_lat"]):
        raise ValueError(
            f"Latitude {v} outside Brazil [{BRAZIL_BOUNDS['min_lat']}, {BRAZIL_BOUNDS['max_lat']}]"
        )
    return v


def validate_brazil_longitude(v: float) -> float:
    if not (BRAZIL_BOUNDS["min_lon"] <= v <= BRAZIL_BOUNDS["max_lon"]):
        raise ValueError(
            f"Longitude {v} outside Brazil [{BRAZIL_BOUNDS['min_lon']}, {BRAZIL_BOUNDS['max_lon']}]"
        )
    return v


def validate_state_code(v: str) -> str:
    if v.upper() not in STATE_CODES:
        raise ValueError(f"Unknown state code '{v}'. Valid: {STATE_CODES}")
    return v.upper()


def validate_biome_id(v: str) -> str:
    if v.lower() not in BIOME_IDS:
        raise ValueError(f"Unknown biome '{v}'. Valid: {BIOME_IDS}")
    return v.lower()


def validate_date_range(start: date, end: date, max_months: int = 24) -> None:
    if start > end:
        raise ValueError(f"start ({start}) must be on or before end ({end})")
    delta_days = (end - start).days
    if delta_days > max_months * 31:
        raise ValueError(
            f"Date range spans {delta_days} days, exceeding {max_months}-month maximum"
        )


def validate_confidence_level(v: float) -> float:
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"confidence_level {v} must be in [0.0, 1.0]")
    return v


class BrazilLatitude(float):
    """Pydantic-compatible type for Brazil-bounded latitude."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.float_schema(
            ge=BRAZIL_BOUNDS["min_lat"],
            le=BRAZIL_BOUNDS["max_lat"],
        )


class BrazilLongitude(float):
    """Pydantic-compatible type for Brazil-bounded longitude."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.float_schema(
            ge=BRAZIL_BOUNDS["min_lon"],
            le=BRAZIL_BOUNDS["max_lon"],
        )
