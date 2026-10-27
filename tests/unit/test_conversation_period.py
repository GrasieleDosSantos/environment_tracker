"""Unit tests for period resolution in conversation_engine._resolve_period."""

from __future__ import annotations

from datetime import date

from src.services.conversation.conversation_engine import _resolve_period
from src.services.conversation.query_parser import ParsedQuery

TODAY = date(2026, 10, 27)


def test_current_year_is_year_to_date_and_prodes_pending():
    p = _resolve_period(ParsedQuery(raw_text="", target_year=2026), TODAY)
    assert (p.start, p.end) == (date(2026, 1, 1), TODAY)
    assert p.long_term
    assert (p.prodes_start, p.prodes_end) == (2023, 2025)


def test_past_year_covers_full_calendar_year():
    p = _resolve_period(ParsedQuery(raw_text="", target_year=2024), TODAY)
    assert (p.start, p.end) == (date(2024, 1, 1), date(2024, 12, 31))
    assert (p.prodes_start, p.prodes_end) == (2022, 2024)


def test_no_scope_keeps_30_day_default():
    p = _resolve_period(ParsedQuery(raw_text=""), TODAY)
    assert (p.start, p.end) == (date(2026, 9, 27), TODAY)
    assert not p.long_term
    assert p.prodes_end == 2025


def test_relative_scope_unchanged():
    p = _resolve_period(ParsedQuery(raw_text="", temporal_scope="last_5_years"), TODAY)
    assert p.long_term
    assert (p.prodes_start, p.prodes_end) == (2021, 2025)
