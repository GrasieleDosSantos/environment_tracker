"""Basemap tile source shared by the Folium map and Plotly map charts.

CARTO Positron is used when ``CARTO_BASEMAPS_API_KEY`` is set (CARTO stopped
serving keyless raster tiles on 2026-09-25 and returns an "API KEY REQUIRED"
placeholder instead). Without a key, OpenStreetMap tiles are used so maps
never show the placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.settings import get_settings

_CARTO_POSITRON_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png?key={key}"
_CARTO_SUBDOMAINS = "abcd"
_CARTO_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)

_OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
_OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)


@dataclass(frozen=True)
class Basemap:
    url: str            # XYZ template; may contain {s} (see ``subdomains``)
    subdomains: str     # characters substituted for {s}; empty if unused
    attribution: str

    def tile_urls(self) -> list[str]:
        """Concrete URLs with {s} expanded — for clients without subdomain support (Plotly)."""
        if not self.subdomains:
            return [self.url]
        return [self.url.replace("{s}", s) for s in self.subdomains]


def get_basemap() -> Basemap:
    """Return CARTO Positron if a key is configured, else OpenStreetMap."""
    key = get_settings().carto_basemaps_api_key.strip()
    if key:
        return Basemap(
            url=_CARTO_POSITRON_URL.replace("{key}", key),
            subdomains=_CARTO_SUBDOMAINS,
            attribution=_CARTO_ATTRIBUTION,
        )
    return Basemap(url=_OSM_URL, subdomains="", attribution=_OSM_ATTRIBUTION)
