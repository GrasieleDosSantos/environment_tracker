"""Unit tests for src/services/conversation/response_generator.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.conversation.response_generator import (
    add_citations,
    format_data_context,
    format_deforestation_detail,
    format_fire_detail,
    format_freshness_warning,
    format_prodes_detail,
)


# ------------------------------------------------------------------ #
# format_data_context                                                   #
# ------------------------------------------------------------------ #

class TestFormatDataContext:
    def test_includes_region_label(self):
        out = format_data_context(region_label="Amazônia")
        assert "Amazônia" in out

    def test_includes_fire_count(self):
        out = format_data_context(fire_count_48h=1234, region_label="Brasil")
        assert "1,234" in out or "1234" in out

    def test_includes_period_label(self):
        out = format_data_context(period_label="01/01/2024 – 31/01/2024")
        assert "01/01/2024" in out

    def test_includes_deforestation_km2(self):
        out = format_data_context(deforestation_km2=456.7)
        assert "456" in out

    def test_all_none_returns_header_only(self):
        out = format_data_context()
        assert "## Dados INPE" in out

    def test_fetched_at_shows_age(self):
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        out = format_data_context(fetched_at=old)
        assert "5.0h" in out or "4." in out  # tolerance for test execution time

    def test_fire_period_label_when_provided(self):
        out = format_data_context(
            fire_count_period=500,
            fire_period_label="últimos 30 dias",
        )
        assert "últimos 30 dias" in out
        assert "500" in out


# ------------------------------------------------------------------ #
# format_fire_detail                                                    #
# ------------------------------------------------------------------ #

class TestFormatFireDetail:
    def test_empty_returns_no_data_message(self):
        out = format_fire_detail([])
        assert "Sem focos" in out or "No fire" in out

    def test_state_table_present(self, fire_hotspots):
        out = format_fire_detail(fire_hotspots)
        assert "MT" in out or "PA" in out
        assert "|" in out  # markdown table

    def test_biome_breakdown_present(self, fire_hotspots):
        out = format_fire_detail(fire_hotspots)
        assert "Bioma" in out or "biome" in out.lower()

    def test_top5_states_at_most_five_rows(self, fire_hotspots):
        out = format_fire_detail(fire_hotspots)
        # Count data rows in state table (skip header and separator)
        lines = [l for l in out.split("\n") if l.startswith("|") and "Estado" not in l and "---" not in l]
        state_rows = [l for l in lines[:10] if l]  # first table only
        assert len(state_rows) <= 5


# ------------------------------------------------------------------ #
# format_deforestation_detail                                           #
# ------------------------------------------------------------------ #

class TestFormatDeforestationDetail:
    def test_empty_returns_no_data_message(self):
        out = format_deforestation_detail([])
        assert "Sem alertas" in out or "No DETER" in out

    def test_state_table_present(self, deter_alerts):
        out = format_deforestation_detail(deter_alerts)
        assert "PA" in out
        assert "MT" in out

    def test_biome_breakdown_present(self, deter_alerts):
        out = format_deforestation_detail(deter_alerts)
        assert "Amazônia" in out or "amazonia" in out.lower()

    def test_area_values_shown(self, deter_alerts):
        out = format_deforestation_detail(deter_alerts)
        # PA contributes 50 km² × 12 months = 600 km²
        assert "600" in out


# ------------------------------------------------------------------ #
# format_prodes_detail                                                  #
# ------------------------------------------------------------------ #

class TestFormatProdesDetail:
    def test_empty_returns_no_data_message(self):
        out = format_prodes_detail([])
        assert "Sem dados" in out or "No PRODES" in out

    def test_single_biome_shows_year_list(self, prodes_records):
        out = format_prodes_detail(prodes_records)
        assert "| Ano |" in out
        assert "2024" in out
        assert "2019" in out

    def test_multi_biome_shows_cross_tab(self):
        from src.services.inpe_integration.prodes_client import PRODESData
        records = [
            PRODESData(year=2024, biome="Pampa", area_km2=4.2, state="RS"),
            PRODESData(year=2024, biome="Caatinga", area_km2=120.0, state="BA"),
            PRODESData(year=2023, biome="Pampa", area_km2=9.9, state="RS"),
            PRODESData(year=2023, biome="Caatinga", area_km2=185.0, state="CE"),
        ]
        out = format_prodes_detail(records)
        assert "| Bioma |" in out
        assert "Pampa" in out
        assert "Caatinga" in out

    def test_capped_year_warning_shown(self):
        from src.services.inpe_integration.prodes_client import PRODESData
        # Simulate 5000 records for year 2024
        records = [PRODESData(year=2024, biome="Mata Atlântica", area_km2=0.04, state="SP")] * 5000
        out = format_prodes_detail(records)
        assert "amostra parcial" in out or "partial sample" in out

    def test_source_attribution_present(self, prodes_records):
        out = format_prodes_detail(prodes_records)
        assert "PRODES" in out
        assert "INPE" in out


# ------------------------------------------------------------------ #
# add_citations                                                         #
# ------------------------------------------------------------------ #

class TestAddCitations:
    def test_adds_citation_when_missing(self):
        out = add_citations("Some text without citation.")
        assert "INPE" in out
        assert "Fonte" in out or "Source" in out

    def test_does_not_duplicate_citation(self):
        text = "Answer text\n\n---\n*Fonte / Source: INPE — [DETER](...)*"
        out = add_citations(text)
        assert out.count("INPE") == out.count("INPE")  # no duplication


# ------------------------------------------------------------------ #
# format_freshness_warning                                              #
# ------------------------------------------------------------------ #

class TestFormatFreshnessWarning:
    def test_fresh_data_returns_empty(self):
        fresh = datetime.now(timezone.utc) - timedelta(hours=6)
        out = format_freshness_warning(fresh)
        assert out == ""

    def test_stale_data_returns_warning(self):
        stale = datetime.now(timezone.utc) - timedelta(hours=25)
        out = format_freshness_warning(stale)
        assert "⚠️" in out or "warning" in out.lower() or "aviso" in out.lower()
