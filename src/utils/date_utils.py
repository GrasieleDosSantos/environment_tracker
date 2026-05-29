from datetime import date, datetime, timedelta, timezone

import pytz

BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

_RELATIVE_PRESETS: dict[str, int] = {
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
    "last_6_months": 180,
    "last_12_months": 365,
    "last_24_months": 730,
}


def now_brazil() -> datetime:
    return datetime.now(tz=BRAZIL_TZ)


def today_brazil() -> date:
    return now_brazil().date()


def resolve_relative_preset(preset: str) -> tuple[date, date]:
    """Return (start, end) date for a named relative preset."""
    if preset not in _RELATIVE_PRESETS:
        raise ValueError(f"Unknown preset '{preset}'. Valid: {list(_RELATIVE_PRESETS)}")
    end = today_brazil()
    start = end - timedelta(days=_RELATIVE_PRESETS[preset])
    return start, end


def parse_date_range(
    start: str | date | datetime | None,
    end: str | date | datetime | None,
    preset: str | None = None,
) -> tuple[date, date]:
    """Parse a date range from string ISO dates, date objects, or a preset name."""
    if preset:
        return resolve_relative_preset(preset)
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    if start is None:
        start = today_brazil() - timedelta(days=30)
    if end is None:
        end = today_brazil()
    if start > end:
        raise ValueError(f"start ({start}) must be <= end ({end})")
    return start, end


def is_stale(timestamp: datetime, threshold_hours: int = 12) -> bool:
    """Return True if timestamp is older than threshold_hours."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = datetime.now(tz=timezone.utc) - timestamp
    return age.total_seconds() > threshold_hours * 3600


def format_relative_age(timestamp: datetime) -> str:
    """Return a human-friendly relative age string in Portuguese."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = datetime.now(tz=timezone.utc) - timestamp
    minutes = int(age.total_seconds() / 60)
    if minutes < 60:
        return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24:
        return f"há {hours} hora{'s' if hours != 1 else ''}"
    days = hours // 24
    return f"há {days} dia{'s' if days != 1 else ''}"
