from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config.constants import BIOME_IDS, BRAZIL_BOUNDS, STATE_CODES, RegionType


class Coordinates(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (BRAZIL_BOUNDS["min_lat"] <= v <= BRAZIL_BOUNDS["max_lat"]):
            raise ValueError(
                f"Latitude {v} outside Brazil bounds "
                f"[{BRAZIL_BOUNDS['min_lat']}, {BRAZIL_BOUNDS['max_lat']}]"
            )
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not (BRAZIL_BOUNDS["min_lon"] <= v <= BRAZIL_BOUNDS["max_lon"]):
            raise ValueError(
                f"Longitude {v} outside Brazil bounds "
                f"[{BRAZIL_BOUNDS['min_lon']}, {BRAZIL_BOUNDS['max_lon']}]"
            )
        return v


class BoundingBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    @field_validator("max_lat")
    @classmethod
    def max_lat_gt_min(cls, v: float, info: Any) -> float:
        if "min_lat" in info.data and v <= info.data["min_lat"]:
            raise ValueError("max_lat must be greater than min_lat")
        return v

    @field_validator("max_lon")
    @classmethod
    def max_lon_gt_min(cls, v: float, info: Any) -> float:
        if "min_lon" in info.data and v <= info.data["min_lon"]:
            raise ValueError("max_lon must be greater than min_lon")
        return v

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


class GeographicRegion(BaseModel):
    region_id: str
    region_type: RegionType
    name: str
    polygon_geometry: dict[str, Any] | None = None
    parent_region: str | None = None
    area_km2: float | None = None

    @field_validator("region_id")
    @classmethod
    def validate_state_code(cls, v: str, info: Any) -> str:
        region_type = info.data.get("region_type")
        if region_type == RegionType.STATE and v.upper() not in STATE_CODES:
            raise ValueError(f"Unknown state code: {v}. Valid codes: {STATE_CODES}")
        if region_type == RegionType.BIOME and v.lower() not in BIOME_IDS:
            raise ValueError(f"Unknown biome id: {v}. Valid ids: {BIOME_IDS}")
        return v


class Biome(BaseModel):
    biome_id: str
    name: str
    name_en: str
    representative_states: list[str] = Field(default_factory=list)
    area_km2: float | None = None
    description: str | None = None

    @field_validator("biome_id")
    @classmethod
    def validate_biome_id(cls, v: str) -> str:
        if v.lower() not in BIOME_IDS:
            raise ValueError(f"Unknown biome: {v}. Valid: {BIOME_IDS}")
        return v.lower()
