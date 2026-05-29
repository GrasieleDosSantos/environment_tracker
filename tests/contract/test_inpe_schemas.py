"""Contract tests — verify live INPE WFS endpoints return the expected schema.

These tests make real HTTP requests to TerraBrasilis and BDQueimadas.
They are skipped automatically in CI (SKIP_CONTRACT_TESTS=true) or when the
services are unreachable, so they never block a build.

Run manually with:
    uv run pytest tests/contract/ -v
"""

from __future__ import annotations

import os

import pytest

# Skip the entire module in CI or when explicitly opted out
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_CONTRACT_TESTS", "false").lower() == "true"
    or os.getenv("CI", "false").lower() == "true",
    reason="Contract tests skipped (CI or SKIP_CONTRACT_TESTS=true)",
)


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _skip_on_network_error(fn):
    """Decorator: skip test when the service is unreachable (network/timeout)."""
    import functools
    import httpx

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
            if "connect" in str(exc).lower() or "timeout" in str(exc).lower():
                pytest.skip(f"Service unreachable: {exc}")
            raise

    return wrapper


# ------------------------------------------------------------------ #
# DETER contract                                                        #
# ------------------------------------------------------------------ #

class TestDETERContract:
    @_skip_on_network_error
    def test_deter_amazon_returns_features(self):
        from src.services.inpe_integration.deter_client import DETERClient
        import asyncio

        async def _fetch():
            async with DETERClient() as client:
                return await client.fetch_recent_alerts(days=7, count=10)

        alerts = asyncio.run(_fetch())
        assert len(alerts) > 0, "Expected at least one DETER alert in the last 7 days"

    @_skip_on_network_error
    def test_deter_alert_has_required_fields(self):
        from src.services.inpe_integration.deter_client import DETERClient
        import asyncio

        async def _fetch():
            async with DETERClient() as client:
                return await client.fetch_recent_alerts(days=30, count=5)

        alerts = asyncio.run(_fetch())
        if not alerts:
            pytest.skip("No DETER alerts returned — cannot validate schema")

        for alert in alerts:
            assert alert.view_date is not None, "view_date must be populated"
            assert alert.area_km2 is not None, "area_km2 must be populated"
            assert alert.state is not None, "state must be populated"

    @_skip_on_network_error
    def test_deter_cerrado_layer_accessible(self):
        from src.services.inpe_integration.deter_client import DETERCerradoClient
        import asyncio

        async def _fetch():
            async with DETERCerradoClient() as client:
                return await client.fetch_recent_alerts(days=30, count=5)

        alerts = asyncio.run(_fetch())
        # May be empty in off-season; just verify no exception was raised
        assert isinstance(alerts, list)


# ------------------------------------------------------------------ #
# PRODES contract                                                       #
# ------------------------------------------------------------------ #

class TestPRODESContract:
    @_skip_on_network_error
    def test_prodes_amazon_returns_records(self):
        from src.services.inpe_integration.prodes_client import PRODESClient
        import asyncio

        async def _fetch():
            async with PRODESClient() as client:
                return await client.fetch_deforestation_by_period(
                    start_year=2023, end_year=2024, count=5
                )

        records = asyncio.run(_fetch())
        assert len(records) > 0

    @_skip_on_network_error
    def test_prodes_record_has_area_km_field(self):
        from src.services.inpe_integration.prodes_client import PRODESClient
        import asyncio

        async def _fetch():
            async with PRODESClient() as client:
                return await client.fetch_deforestation_by_period(
                    start_year=2024, end_year=2024, count=5
                )

        records = asyncio.run(_fetch())
        if not records:
            pytest.skip("No PRODES records returned")

        for r in records:
            assert r.area_km2 is not None, "area_km2 (from area_km) must be parsed"
            assert r.year is not None, "year must be parsed"

    @pytest.mark.parametrize("biome_id", ["pampa", "caatinga", "mata_atlantica", "pantanal"])
    @_skip_on_network_error
    def test_prodes_non_amazon_biomes_accessible(self, biome_id):
        from src.services.inpe_integration.prodes_client import (
            _PRODES_BIOME_LAYERS,
            _PRODES_BIOME_ENDPOINTS,
            PRODESNonAmazonClient,
        )
        import asyncio

        layer = _PRODES_BIOME_LAYERS[biome_id]
        endpoint = _PRODES_BIOME_ENDPOINTS[biome_id]

        async def _fetch():
            async with PRODESNonAmazonClient(endpoint=endpoint, layer=layer) as client:
                return await client.fetch_by_period(start_year=2024, end_year=2024, count=3)

        records = asyncio.run(_fetch())
        assert isinstance(records, list), f"{biome_id} layer should return a list"


# ------------------------------------------------------------------ #
# FOGO contract                                                         #
# ------------------------------------------------------------------ #

class TestFOGOContract:
    @_skip_on_network_error
    def test_fogo_48h_layer_returns_hotspots(self):
        from src.services.inpe_integration.fogo_client import FogoClient
        import asyncio

        async def _fetch():
            async with FogoClient() as client:
                return await client.fetch_current_hotspots(count=10)

        hotspots = asyncio.run(_fetch())
        assert len(hotspots) > 0, "Expected fire hotspots in the 48h layer"

    @_skip_on_network_error
    def test_fogo_hotspot_has_coordinates(self):
        from src.services.inpe_integration.fogo_client import FogoClient
        import asyncio

        async def _fetch():
            async with FogoClient() as client:
                return await client.fetch_current_hotspots(count=5)

        hotspots = asyncio.run(_fetch())
        if not hotspots:
            pytest.skip("No fire hotspots returned")

        for h in hotspots:
            # Latitude must be within Brazil's bounding box
            if h.latitude is not None:
                assert -35.0 <= h.latitude <= 5.5, f"Latitude {h.latitude} out of Brazil bounds"
            if h.longitude is not None:
                assert -74.0 <= h.longitude <= -28.0, f"Longitude {h.longitude} out of Brazil bounds"
