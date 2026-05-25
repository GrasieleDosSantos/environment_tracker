from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.config.constants import AlertSeverity, AlertStatus, AlertType, DataType, INPESource


class EnvironmentalDataPoint(BaseModel):
    data_point_id: str
    data_type: DataType
    state: str | None = None
    municipality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    biome: str | None = None
    value: float
    unit: str = ""
    collection_date: datetime
    data_source: INPESource
    confidence_level: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_attributes: dict | None = None


class AlertThreshold(BaseModel):
    alert_type: AlertType
    region_id: str | None = None
    biome_id: str | None = None
    threshold_value: float
    unit: str
    is_active: bool = True

    @field_validator("threshold_value")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("threshold_value must be positive")
        return v


class EnvironmentalAlert(BaseModel):
    alert_id: str
    event_type: AlertType
    severity_level: AlertSeverity
    region_id: str | None = None
    biome_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    detection_date: datetime
    description: str
    affected_area_km2: float | None = None
    recommendation: str = ""
    status: AlertStatus = AlertStatus.ACTIVE
    data_source: INPESource
    raw_value: float | None = None
    threshold_value: float | None = None
