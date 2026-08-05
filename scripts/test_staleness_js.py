"""Unit tests for docs/js/staleness.js, executed in a real browser.

Every case pins "now" to a fixed number and derives the timestamp from it, so
these tests do not drift as the real calendar advances.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="staleness.js unit tests need pytest-playwright")

NOW = 1_800_000_000_000


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/staleness.js'); "
        f"return ({body}); }}"
    )


def at(offset_expr: str) -> str:
    """Derive an ISO timestamp from NOW; a positive offset means older data."""
    return f"new Date({NOW} - ({offset_expr})).toISOString()"


def test_data_from_this_morning_is_fresh(page, server):
    got = evaluate(page, server, f"m.staleness({at('20*3600e3')}, {NOW})")
    assert got == {"status": "fresh", "ageDays": None}


def test_exactly_forty_eight_hours_is_still_fresh(page, server):
    got = evaluate(page, server, f"m.staleness({at('48*3600e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_a_minute_past_forty_eight_hours_is_stale(page, server):
    got = evaluate(page, server, f"m.staleness({at('48*3600e3 + 60e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 2}


def test_age_days_floors_instead_of_rounding(page, server):
    got = evaluate(page, server, f"m.staleness({at('84*3600e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 3}


def test_a_missing_timestamp_is_unreadable_not_stale(page, server):
    got = evaluate(page, server, f"m.staleness(null, {NOW})")
    assert got == {"status": "unreadable", "ageDays": None}


def test_a_malformed_timestamp_is_unreadable(page, server):
    got = evaluate(page, server, f"m.staleness('唔係一個日期', {NOW})")
    assert got["status"] == "unreadable"


def test_an_invalid_clock_is_unreadable(page, server):
    got = evaluate(page, server, f"m.staleness({at('1*3600e3')}, NaN)")
    assert got == {"status": "unreadable", "ageDays": None}


def test_a_future_timestamp_says_the_clock_is_wrong(page, server):
    got = evaluate(page, server, f"m.staleness({at('-2*3600e3')}, {NOW})")
    assert got == {"status": "future", "ageDays": None}


def test_small_clock_skew_is_tolerated(page, server):
    got = evaluate(page, server, f"m.staleness({at('-30*60e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_fresh_data_produces_no_message(page, server):
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('1*3600e3')}, {NOW}))")
    assert got == ""


def test_the_stale_message_names_the_age_and_what_to_check(page, server):
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('5*864e5')}, {NOW}))")
    assert "5 日前" in got
    assert "舊快照" in got
    assert "Actions" in got
