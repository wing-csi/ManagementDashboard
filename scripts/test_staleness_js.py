"""Unit tests for the dashboard snapshot-age rule."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright", reason="staleness.js tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/staleness.js'); "
        f"return ({body}); }}"
    )


NOW = "Date.parse('2026-08-05T12:00:00Z')"


def test_exactly_48_hours_is_still_fresh(page, server):
    got = evaluate(page, server, f"m.staleness('2026-08-03T12:00:00Z', {NOW})")
    assert got["status"] == "fresh"


def test_more_than_48_hours_is_stale(page, server):
    got = evaluate(page, server, f"m.staleness('2026-08-03T11:59:59Z', {NOW})")
    assert got["status"] == "stale"
    assert got["ageDays"] == 2


def test_a_bad_timestamp_is_not_misreported_as_old(page, server):
    got = evaluate(page, server, f"m.staleness('not-a-date', {NOW})")
    assert got == {"status": "unreadable", "ageDays": None, "ageHours": None}


def test_a_future_timestamp_has_its_own_status(page, server):
    got = evaluate(page, server, f"m.staleness('2026-08-05T14:00:00Z', {NOW})")
    assert got["status"] == "future"

