"""Unit tests for PRODES dashboard aggregation (no network)."""

from __future__ import annotations

import pytest

from src.services.inpe_integration import prodes_dashboard as pd_mod

_LOINAMES = {
    "lois": [
        {"gid": 1, "name": "uf", "loinames": [
            {"gid": 10, "loiname": "Pará"},
            {"gid": 11, "loiname": "MATO GROSSO"},
            {"gid": 12, "loiname": "Atlantis"},  # unknown → ignored
        ]},
        {"gid": 2, "name": "mun", "loinames": [{"gid": 99, "loiname": "Altamira"}]},
    ]
}


def _period(year: int, features: list[dict]) -> dict:
    return {
        "startDate": {"year": year - 1, "month": 8, "day": 1},
        "endDate": {"year": year, "month": 7, "day": 31},
        "features": features,
    }


_DATA = {
    "periods": [
        _period(2023, [
            {"loi": 1, "loiname": 10, "areas": [{"type": 1, "area": 100.0}]},
            {"loi": 1, "loiname": 11, "areas": [{"type": 1, "area": 50.0}, {"type": 2, "area": 999.0}]},
            {"loi": 1, "loiname": 12, "areas": [{"type": 1, "area": 7.0}]},
            # municipality rows duplicate state totals and must not be summed
            {"loi": 2, "loiname": 99, "areas": [{"type": 1, "area": 100.0}]},
        ]),
        _period(2024, [
            {"loi": 1, "loiname": 10, "areas": [{"type": 1, "area": 80.0}]},
        ]),
    ]
}


def test_state_year_table_uses_state_rows_and_deforestation_type_only():
    table = pd_mod._state_year_table(_DATA, pd_mod._uf_codes(_LOINAMES))
    assert table == {2023: {"PA": 100.0, "MT": 50.0}, 2024: {"PA": 80.0}}


def test_uf_codes_match_names_ignoring_accents_and_case():
    assert pd_mod._uf_codes(_LOINAMES) == {10: "PA", 11: "MT"}


@pytest.fixture
def fake_tables(monkeypatch):
    tables = {
        "amazonia": {2022: {"PA": 10.0, "MT": 5.0}, 2023: {"PA": 100.0, "MT": 50.0}},
        "cerrado": {2023: {"MT": 30.0}},
    }
    monkeypatch.setattr(pd_mod, "_biome_table", lambda biome_id: tables[biome_id])
    return tables


def test_totals_sum_states_per_biome_year(fake_tables):
    recs = pd_mod.fetch_prodes_annual_totals(["amazonia", "cerrado"])
    got = {(r.biome, r.year): r.area_km2 for r in recs}
    assert got == {("Amazônia", 2022): 15.0, ("Amazônia", 2023): 150.0, ("Cerrado", 2023): 30.0}
    assert all(r.state is None for r in recs)


def test_totals_filter_by_state_and_years(fake_tables):
    recs = pd_mod.fetch_prodes_annual_totals(["amazonia", "cerrado"], state="mt", start_year=2023)
    got = {(r.biome, r.year, r.state): r.area_km2 for r in recs}
    assert got == {("Amazônia", 2023, "MT"): 50.0, ("Cerrado", 2023, "MT"): 30.0}


def test_unknown_biome_and_failed_biome_are_skipped(monkeypatch):
    def _boom(biome_id):
        raise RuntimeError("down")
    monkeypatch.setattr(pd_mod, "_biome_table", _boom)
    assert pd_mod.fetch_prodes_annual_totals(["amazonia", "atlantis"]) == []


def test_legal_amazon_rates(monkeypatch):
    table = {2020: {"PA": 5000.0, "MT": 1700.0}, 2021: {"PA": 5200.0, "MT": 2200.0}}
    monkeypatch.setattr(pd_mod, "_cached_table", lambda key, build: table)
    assert pd_mod.fetch_legal_amazon_rates() == {2020: 6700.0, 2021: 7400.0}
    assert pd_mod.fetch_legal_amazon_rates(start_year=2021, state="PA") == {2021: 5200.0}
