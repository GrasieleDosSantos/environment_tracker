from datetime import date

from pydantic import BaseModel, Field

from src.config.constants import DataType, INPESource, TrendDirection


class TimeSeriesData(BaseModel):
    series_id: str
    metric_type: DataType
    time_period_start: date
    time_period_end: date
    value: float
    unit: str = ""
    region_id: str | None = None
    biome_id: str | None = None
    state_code: str | None = None
    data_source: INPESource
    trend_direction: TrendDirection | None = None


class TrendInfo(BaseModel):
    direction: TrendDirection
    slope: float = Field(description="Rate of change per time unit")
    confidence_score: float = Field(ge=0.0, le=1.0)
    change_percentage: float = Field(description="% change over the measured period")
    period_start: date
    period_end: date
    data_points_count: int
    baseline_value: float | None = None
    current_value: float | None = None
