from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model identifier")

    # INPE endpoints
    inpe_deter_endpoint: str = Field(
        default="https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows"
    )
    inpe_prodes_endpoint: str = Field(
        default="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-amz-nb/ows"
    )
    inpe_fogo_endpoint: str = Field(
        default="https://terrabrasilis.dpi.inpe.br/queimadas/geoserver/ows"
    )

    # Database
    database_url: str = Field(default="sqlite:///./environment_tracker.db")

    # Cache
    redis_url: str = Field(default="")
    cache_ttl_default: int = Field(default=3600, description="Default cache TTL in seconds")
    cache_ttl_deter: int = Field(default=86400, description="24h cache for DETER alerts")
    cache_ttl_prodes: int = Field(default=2592000, description="30d cache for PRODES data")
    cache_ttl_fogo: int = Field(default=14400, description="4h cache for fire hotspots")

    # Alert thresholds
    alert_threshold_fires: int = Field(
        default=100, description="Fire hotspots per 24h per region to trigger alert"
    )
    alert_threshold_deforestation: int = Field(
        default=50, description="% above 12-month average to trigger deforestation alert"
    )

    # Rate limits (requests per second)
    rate_limit_deter: float = Field(default=1.0)
    rate_limit_prodes: float = Field(default=2.0)
    rate_limit_fogo: float = Field(default=5.0 / 60.0, description="5 req/min expressed as req/sec")

    # Langfuse
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_endpoint: str = Field(default="https://cloud.langfuse.com")

    # App
    data_freshness_warning_hours: int = Field(
        default=12, description="Warn in conversation if data older than this"
    )
    historical_months: int = Field(default=24, description="Months of history to maintain")

    @property
    def use_redis(self) -> bool:
        return bool(self.redis_url)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
