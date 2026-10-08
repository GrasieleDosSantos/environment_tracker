"""Unit tests for FilterState session migration (legacy dicts, stale classes)."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from src.ui.components import filters


@pytest.fixture
def session(monkeypatch):
    state: dict = {}
    monkeypatch.setattr(filters, "st", SimpleNamespace(session_state=state))
    return state


def test_returns_current_instance_unchanged(session):
    fs = filters.FilterState(biomes=["cerrado"])
    session["filter_state"] = fs
    assert filters.get_filter_state() is fs


def test_migrates_legacy_dict(session):
    session["filter_state"] = {"biome": "amazonia", "state_code": "PA"}
    fs = filters.get_filter_state()
    assert fs.biomes == ["amazonia"]
    assert fs.states == ["PA"]
    assert isinstance(session["filter_state"], filters.FilterState)


def test_migrates_instance_of_previous_class_after_reload(session):
    # Simulate a redeploy: the session holds an instance of the old class
    stale = filters.FilterState(states=["MT"], biomes=["pantanal"], date_preset="last_7_days")
    fake_st = filters.st
    reloaded = importlib.reload(filters)
    reloaded.st = fake_st  # reload re-imports the real streamlit
    session["filter_state"] = stale
    assert not isinstance(stale, reloaded.FilterState)

    fs = reloaded.get_filter_state()

    assert isinstance(fs, reloaded.FilterState)
    assert fs.states == ["MT"]
    assert fs.biomes == ["pantanal"]
    assert fs.date_preset == "last_7_days"
    assert session["filter_state"] is fs
