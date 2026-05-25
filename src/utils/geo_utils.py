from src.config.constants import BRAZIL_BOUNDS


def is_within_brazil(lat: float, lon: float) -> bool:
    """Return True if the coordinates fall within Brazil's bounding box."""
    return (
        BRAZIL_BOUNDS["min_lat"] <= lat <= BRAZIL_BOUNDS["max_lat"]
        and BRAZIL_BOUNDS["min_lon"] <= lon <= BRAZIL_BOUNDS["max_lon"]
    )


def validate_coordinates(lat: float, lon: float) -> None:
    """Raise ValueError if coordinates are outside Brazil's bounding box."""
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude {lat} out of range [-90, 90]")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude {lon} out of range [-180, 180]")
    if not is_within_brazil(lat, lon):
        raise ValueError(
            f"Coordinates ({lat}, {lon}) are outside Brazil's bounding box. "
            f"Expected lat in [{BRAZIL_BOUNDS['min_lat']}, {BRAZIL_BOUNDS['max_lat']}], "
            f"lon in [{BRAZIL_BOUNDS['min_lon']}, {BRAZIL_BOUNDS['max_lon']}]"
        )


def degrees_to_decimal(degrees: float, minutes: float, seconds: float, direction: str) -> float:
    """Convert DMS to decimal degrees."""
    decimal = degrees + minutes / 60 + seconds / 3600
    if direction.upper() in ("S", "W"):
        decimal = -decimal
    return decimal


def bbox_to_wkt(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    """Convert a bounding box to WKT POLYGON string."""
    return (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def get_brazil_bbox_wkt() -> str:
    return bbox_to_wkt(
        BRAZIL_BOUNDS["min_lat"],
        BRAZIL_BOUNDS["min_lon"],
        BRAZIL_BOUNDS["max_lat"],
        BRAZIL_BOUNDS["max_lon"],
    )


def center_of_bbox(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float
) -> tuple[float, float]:
    """Return (lat, lon) center of a bounding box."""
    return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2


BRAZIL_CENTER = center_of_bbox(
    BRAZIL_BOUNDS["min_lat"],
    BRAZIL_BOUNDS["min_lon"],
    BRAZIL_BOUNDS["max_lat"],
    BRAZIL_BOUNDS["max_lon"],
)
