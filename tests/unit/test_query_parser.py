"""Unit tests for src/services/conversation/query_parser.py.

All tests exercise the rule-based extraction path only (no LLM calls).
Short queries (< 3 words) suppress the LLM fallback automatically.
"""

from __future__ import annotations

import pytest

from src.services.conversation.query_parser import (
    ParsedQuery,
    _detect_language,
    _extract_biomes,
    _extract_metrics,
    _extract_states,
    _extract_temporal,
    parse_query,
)


# ------------------------------------------------------------------ #
# Language detection                                                    #
# ------------------------------------------------------------------ #

class TestDetectLanguage:
    def test_portuguese(self):
        lang, conf = _detect_language("Qual é a situação de queimadas no Cerrado?")
        assert lang == "pt"
        assert conf >= 2

    def test_english(self):
        lang, conf = _detect_language("What is the deforestation rate in the Amazon?")
        assert lang == "en"
        assert conf >= 2

    def test_short_ambiguous_returns_pt_default(self):
        lang, _ = _detect_language("ok")
        assert lang == "pt"


# ------------------------------------------------------------------ #
# State extraction                                                      #
# ------------------------------------------------------------------ #

class TestExtractStates:
    def test_single_state_by_code(self):
        states, needs_clarification, _ = _extract_states("Dados de desmatamento em AM")
        assert "AM" in states
        assert not needs_clarification

    def test_single_state_by_name(self):
        states, _, _ = _extract_states("situação de queimadas no Pará")
        assert "PA" in states

    def test_amazonia_legal_expansion(self):
        states, _, _ = _extract_states("queimadas na Amazônia Legal")
        assert len(states) == 9
        assert "AM" in states
        assert "PA" in states

    def test_sao_paulo_resolves_to_sp(self):
        # "São Paulo" is in _STATE_LOOKUP as a direct match → returns SP, not ambiguous
        states, needs_clarification, _ = _extract_states("Dados de São Paulo")
        assert not needs_clarification
        assert "SP" in states

    def test_multiple_states(self):
        states, _, _ = _extract_states("Pará e Mato Grosso têm mais alertas")
        assert "PA" in states
        assert "MT" in states

    def test_no_state_mentioned(self):
        states, needs_clarification, _ = _extract_states("queimadas no cerrado")
        assert not needs_clarification

    def test_rio_ambiguous(self):
        states, needs_clarification, opts = _extract_states("dados do Rio")
        assert needs_clarification


# ------------------------------------------------------------------ #
# Biome extraction                                                      #
# ------------------------------------------------------------------ #

class TestExtractBiomes:
    @pytest.mark.parametrize("text,expected", [
        ("queimadas na Amazônia", "amazonia"),
        ("desmatamento no Cerrado", "cerrado"),
        ("caatinga está sofrendo", "caatinga"),
        ("mata atlântica em risco", "mata_atlantica"),
        ("atlantic forest deforestation", "mata_atlantica"),
        ("pampas queimadas", "pampa"),
        ("pantanal incêndio", "pantanal"),
        ("amazon deforestation", "amazonia"),
    ])
    def test_biome_detected(self, text, expected):
        biomes = _extract_biomes(text)
        assert expected in biomes

    def test_multiple_biomes(self):
        biomes = _extract_biomes("Amazônia e Cerrado têm alertas")
        assert "amazonia" in biomes
        assert "cerrado" in biomes

    def test_no_biome(self):
        biomes = _extract_biomes("quantos focos houve ontem?")
        assert biomes == []


# ------------------------------------------------------------------ #
# Metric extraction                                                     #
# ------------------------------------------------------------------ #

class TestExtractMetrics:
    @pytest.mark.parametrize("text,expected", [
        ("focos de queimada no Cerrado", "fire"),
        ("alertas DETER esta semana", "deforestation"),
        ("taxa de desmatamento no Pará", "deforestation"),
        ("fire hotspots in the Amazon", "fire"),
        ("deforestation cleared in MT", "deforestation"),
        ("cobertura de vegetação", "vegetation"),
    ])
    def test_metric_detected(self, text, expected):
        metrics = _extract_metrics(text)
        assert expected in metrics

    def test_no_metric(self):
        metrics = _extract_metrics("olá tudo bem")
        assert metrics == []


# ------------------------------------------------------------------ #
# Temporal scope extraction                                             #
# ------------------------------------------------------------------ #

class TestExtractTemporal:
    @pytest.mark.parametrize("text,expected", [
        ("queimadas hoje", "last_1_day"),
        ("focos nas últimas 24h", "last_1_day"),
        ("últimos 7 dias", "last_7_days"),
        ("last 7 days", "last_7_days"),
        ("últimas duas semanas", "last_14_days"),
        ("últimos 30 dias", "last_30_days"),
        ("last 30 days", "last_30_days"),
        ("últimos 90 dias", "last_90_days"),
        ("este ano", "last_year"),
        ("últimos 12 meses", "last_12_months"),
        ("last 12 months", "last_12_months"),
        # Multi-year scopes
        ("últimos 3 anos", "last_3_years"),
        ("últimos 5 anos", "last_5_years"),
        ("last 5 years", "last_5_years"),
        ("últimos 7 anos", "last_7_years"),
        ("last 10 years", "last_10_years"),
        ("últimos 10 anos", "last_10_years"),
        ("últimos 15 anos", "last_10_years"),
    ])
    def test_scope_extracted(self, text, expected):
        scope = _extract_temporal(text)
        assert scope == expected

    def test_no_temporal_returns_none(self):
        scope = _extract_temporal("taxa de desmatamento geral")
        assert scope is None


# ------------------------------------------------------------------ #
# parse_query end-to-end (rule-based path, no LLM)                    #
# ------------------------------------------------------------------ #

class TestParseQuery:
    def test_fire_query_pt(self):
        pq = parse_query("queimadas PA")
        assert "PA" in pq.states
        assert "fire" in pq.metrics

    def test_deforestation_amazon_query(self):
        pq = parse_query("desmatamento amazônia")
        assert "amazonia" in pq.biomes
        assert "deforestation" in pq.metrics

    def test_language_pt(self):
        pq = parse_query("Qual é a situação de queimadas no Cerrado esta semana?")
        assert pq.language == "pt"
        assert pq.temporal_scope == "last_7_days"
        assert "cerrado" in pq.biomes

    def test_language_en(self):
        pq = parse_query("What is the deforestation rate in the Amazon last 30 days?")
        assert pq.language == "en"
        assert pq.temporal_scope == "last_30_days"

    def test_amazonia_legal_expands_to_nine_states(self):
        pq = parse_query("queimadas amazônia legal")
        assert len(pq.states) == 9

    def test_default_metrics_when_none_detected(self):
        pq = parse_query("PA")
        assert "fire" in pq.metrics or "deforestation" in pq.metrics

    def test_multi_year_scope_parsed(self):
        pq = parse_query("desmatamento mata atlântica últimos 10 anos")
        assert pq.temporal_scope == "last_10_years"
        assert "mata_atlantica" in pq.biomes

    def test_needs_clarification_rio(self):
        # "rio" alone is ambiguous (RJ / RN / RS) — does not match any full state name
        pq = parse_query("dados do Rio")
        assert pq.needs_clarification
        assert len(pq.clarification_options) > 0
