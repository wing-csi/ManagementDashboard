"""Unit tests for docs/js/staleness.js, executed in a real browser.

Same approach as test_plan_dates_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

Every case pins "now" to a fixed number and derives the timestamp from it, so
these tests do not drift as the real calendar advances. That is the same
property the module's signature exists to give the frontend tests.

Run:  python -m pytest scripts/test_staleness_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="staleness.js unit tests need pytest-playwright")

# 一個固定嘅「而家」。實際係邊一日唔重要 —— 重要係佢唔郁。
NOW = 1_800_000_000_000


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/staleness.js'); "
        f"return ({body}); }}"
    )


def at(offset_expr: str) -> str:
    """由 NOW 推出一個 ISO 時間戳,offset 用 JS 表達式寫(正數 = 舊)。"""
    return f"new Date({NOW} - ({offset_expr})).toISOString()"


def test_data_from_this_morning_is_fresh(page, server):
    """20 個鐘大係正常 —— cron 21:00 UTC 行,一日入面大部分時間都係咁。"""
    got = evaluate(page, server, f"m.staleness({at('20*3600e3')}, {NOW})")
    assert got == {"status": "fresh", "ageDays": None}


def test_exactly_forty_eight_hours_is_still_fresh(page, server):
    """界線係 `>`,唔係 `>=`。啱啱 48 鐘唔算過期。"""
    got = evaluate(page, server, f"m.staleness({at('48*3600e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_a_minute_past_forty_eight_hours_is_stale(page, server):
    got = evaluate(page, server, f"m.staleness({at('48*3600e3 + 60e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 2}


def test_age_days_floors_instead_of_rounding(page, server):
    """84 個鐘係 3.5 日 —— 要出「3 日前」,唔係 4。門檻用毫秒判,呢個數淨係
    攞嚟寫嗰句字。"""
    got = evaluate(page, server, f"m.staleness({at('84*3600e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 3}


def test_a_missing_timestamp_is_unreadable_not_stale(page, server):
    """冇時間戳唔等於數據舊 —— 要改嘅嘢完全唔同,所以要分得開。"""
    got = evaluate(page, server, f"m.staleness(null, {NOW})")
    assert got == {"status": "unreadable", "ageDays": None}


def test_a_malformed_timestamp_is_unreadable(page, server):
    got = evaluate(page, server, f"m.staleness('唔係一個日期', {NOW})")
    assert got["status"] == "unreadable"


def test_a_future_timestamp_says_the_clock_is_wrong(page, server):
    """時間戳喺未來代表有個 clock 唔啱,唔係數據舊。講成「舊咗」就係講假嘢。"""
    got = evaluate(page, server, f"m.staleness({at('-2*3600e3')}, {NOW})")
    assert got == {"status": "future", "ageDays": None}


def test_small_clock_skew_is_tolerated(page, server):
    """半個鐘嘅偏差好平常 —— 唔可以為咗佢彈個警告出嚟。"""
    got = evaluate(page, server, f"m.staleness({at('-30*60e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_fresh_data_produces_no_message(page, server):
    """冇嘢講嗰陣要出空字串,唔可以出 'undefined' 落個 banner 度。"""
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('1*3600e3')}, {NOW}))")
    assert got == ""


def test_the_stale_message_names_the_age_and_what_to_check(page, server):
    """個 banner 要講得出係幾耐同埋去邊度查 —— 淨係話「舊咗」等於冇講。"""
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('5*864e5')}, {NOW}))")
    assert "5 日前" in got
    assert "Actions" in got
