"""Unit tests for INPE Pydantic response models.

Validates that GeoJSON Feature dicts are parsed correctly into flat models
and that field aliases / fallback lookups work as documented.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.services.inpe_integration.deter_client import DETERAlert
from src.services.inpe_integration.fogo_client import FireHotspot
from src.services.inpe_integration.prodes_client import PRODESData, PRODESNonAmazonData


# ------------------------------------------------------------------ #
# DETERAlert                                                            #
# ------------------------------------------------------------------ #

class TestDETERAlert:
    _FEATURE = {
        "type": "Feature",
        "properties": {
            "VIEW_DATE": "2024-06-15",
            "CLASSNAME": "DESMATAMENTO_VEG",
            "UF": "PA",
            "AREAMUNKM": 23.5,
            "MUNICIPIO": "Altamira",
            "BIOMA": "Amazônia",
        },
        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0]]]]},
    }

    def test_parses_from_geojson_feature(self):
        alert = DETERAlert.model_validate(self._FEATURE)
        assert alert.view_date == date(2024, 6, 15)
        assert alert.classname == "DESMATAMENTO_VEG"
        assert alert.state == "PA"
        assert alert.area_km2 == pytest.approx(23.5)
        assert alert.municipality == "Altamira"
        assert alert.biome == "Amazônia"

    def test_parses_lowercase_property_keys(self):
        feat = {
            "properties": {
                "view_date": "2024-01-10",
                "classname": "DEGRADACAO",
                "uf": "MT",
                "areamunkm": 5.0,
            },
            "geometry": {},
        }
        alert = DETERAlert.model_validate(feat)
        assert alert.state == "MT"
        assert alert.view_date == date(2024, 1, 10)

    def test_invalid_date_results_in_none(self):
        feat = {"properties": {"VIEW_DATE": "not-a-date"}, "geometry": {}}
        alert = DETERAlert.model_validate(feat)
        assert alert.view_date is None

    def test_missing_all_fields_is_valid(self):
        alert = DETERAlert.model_validate({"properties": {}, "geometry": {}})
        assert alert.area_km2 is None
        assert alert.state is None

    def test_direct_field_construction_bypasses_validator(self):
        alert = DETERAlert(view_date=date(2024, 3, 1), state="AM", area_km2=10.0)
        assert alert.state == "AM"


# ------------------------------------------------------------------ #
# FireHotspot                                                           #
# ------------------------------------------------------------------ #

class TestFireHotspot:
    # BDQueimadas WFS uses lowercase snake_case property names
    _FEATURE = {
        "type": "Feature",
        "properties": {
            "latitude": -10.5,
            "longitude": -55.2,
            "estado": "MATO GROSSO",   # full name; sigla extracted by helper
            "bioma": "Amazônia",
            "data_pas": "2024-06-01",
            "satelite": "AQUA_M-T",
        },
        "geometry": {"type": "Point", "coordinates": [-55.2, -10.5]},
    }

    def test_parses_from_geojson_feature(self):
        h = FireHotspot.model_validate(self._FEATURE)
        assert h.biome == "Amazônia"
        assert h.latitude == pytest.approx(-10.5)
        assert h.longitude == pytest.approx(-55.2)

    def test_direct_construction(self):
        from datetime import datetime, timezone
        h = FireHotspot(
            latitude=-12.0,
            longitude=-48.0,
            state="TO",
            biome="Cerrado",
            detection_time=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        assert h.state == "TO"

    def test_missing_state_is_none(self):
        feat = {"properties": {"LAT": -5.0, "LON": -60.0}, "geometry": {}}
        h = FireHotspot.model_validate(feat)
        assert h.state is None


# ------------------------------------------------------------------ #
# PRODESData                                                            #
# ------------------------------------------------------------------ #

class TestPRODESData:
    _FEATURE = {
        "type": "Feature",
        "properties": {
            "year": 2023,
            "state": "PA",
            "biome": "Amazônia",
            "area_km": 45.2,       # actual PRODES field name
        },
        "geometry": {"type": "MultiPolygon", "coordinates": []},
    }

    def test_parses_area_km_field(self):
        rec = PRODESData.model_validate(self._FEATURE)
        assert rec.area_km2 == pytest.approx(45.2)

    def test_parses_year(self):
        rec = PRODESData.model_validate(self._FEATURE)
        assert rec.year == 2023

    def test_parses_state(self):
        rec = PRODESData.model_validate(self._FEATURE)
        assert rec.state == "PA"

    def test_year_from_string(self):
        feat = {"properties": {"year": "2022", "area_km": 10.0}, "geometry": {}}
        rec = PRODESData.model_validate(feat)
        assert rec.year == 2022

    def test_non_numeric_year_is_none(self):
        feat = {"properties": {"year": "N/A", "area_km": 5.0}, "geometry": {}}
        rec = PRODESData.model_validate(feat)
        assert rec.year is None

    def test_direct_construction(self):
        rec = PRODESData(year=2024, state="RS", biome="Pampa", area_km2=4.2)
        assert rec.biome == "Pampa"
        assert rec.area_km2 == pytest.approx(4.2)


# ------------------------------------------------------------------ #
# PRODESNonAmazonData                                                   #
# ------------------------------------------------------------------ #

class TestPRODESNonAmazonData:
    def test_parses_image_date(self):
        feat = {
            "properties": {
                "image_date": "2023-11-01",
                "area_km": 12.0,
                "state": "BA",
            },
            "geometry": {},
        }
        rec = PRODESNonAmazonData.model_validate(feat)
        assert rec.image_date == date(2023, 11, 1)
        assert rec.year == 2023

    def test_year_fallback_from_image_date(self):
        feat = {
            "properties": {"image_date": "2022-08-15", "area_km": 5.0},
            "geometry": {},
        }
        rec = PRODESNonAmazonData.model_validate(feat)
        assert rec.year == 2022
