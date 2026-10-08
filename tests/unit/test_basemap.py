"""Unit tests for basemap tile selection (CARTO with key, OSM fallback)."""

from __future__ import annotations

import pytest

from src.config.settings import Settings
from src.ui.components import basemap as basemap_mod


@pytest.fixture
def with_key(monkeypatch):
    def _set(key: str) -> None:
        monkeypatch.setattr(
            basemap_mod, "get_settings", lambda: Settings(carto_basemaps_api_key=key)
        )
    return _set


def test_uses_carto_with_key(with_key):
    with_key("abc123")
    bm = basemap_mod.get_basemap()
    assert "basemaps.cartocdn.com/light_all" in bm.url
    assert bm.url.endswith("?key=abc123")
    assert "CARTO" in bm.attribution


def test_falls_back_to_osm_without_key(with_key):
    with_key("")
    bm = basemap_mod.get_basemap()
    assert bm.url == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert "carto" not in bm.url
    assert bm.tile_urls() == [bm.url]


def test_blank_key_treated_as_missing(with_key):
    with_key("   ")
    assert "openstreetmap" in basemap_mod.get_basemap().url


def test_tile_urls_expand_subdomains(with_key):
    with_key("k")
    urls = basemap_mod.get_basemap().tile_urls()
    assert len(urls) == 4
    assert all("{s}" not in u for u in urls)
    assert urls[0].startswith("https://a.basemaps.cartocdn.com/")


def test_heatmap_uses_basemap_tiles(with_key):
    import pandas as pd

    from src.ui.components import charts

    with_key("k")
    fig = charts.spatial_heatmap(pd.DataFrame({"lat": [-10.0], "lon": [-50.0]}), "lat", "lon", "t")
    layer = fig.layout.mapbox.layers[0]
    assert fig.layout.mapbox.style == "white-bg"
    assert all("?key=k" in u for u in layer.source)
