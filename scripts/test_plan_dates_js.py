"""Unit tests for docs/js/plan-dates.js, executed in a real browser.

Same approach as test_burndown_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

What is under test is the single question both the burndown and the timeline
have to answer the same way: 「呢份 plan 有冇一個畫得出嘅終點,冇嘅話係
點解」. Two copies of this rule drifting apart is the whole reason it moved
into its own module.

Run:  python -m pytest scripts/test_plan_dates_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="plan-dates.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/plan-dates.js'); "
        f"return ({body}); }}"
    )


HIST = "history: [{date: '2026-08-01', done: 0, total: 10}]"


def test_a_plan_with_a_usable_due_has_no_reason(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-09-18'}})")
    assert got == {"start": "2026-08-01", "due": "2026-09-18", "dueReason": None}


def test_no_history_is_its_own_reason(page, server):
    """舊 metrics.json 冇 history — 同「有 history 但冇 due:」要分得開。"""
    got = evaluate(page, server, "m.resolvePlanWindow({due_max: '2026-09-18'})")
    assert got["start"] is None
    assert got["dueReason"] == "no-history"


def test_a_plan_without_any_due_says_no_due(page, server):
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}}})")
    assert got["due"] is None
    assert got["dueReason"] == "no-due"


def test_a_calendar_invalid_due_is_unusable_not_absent(page, server):
    """2026-02-30 唔會出 NaN — JS 靜靜哋當佢 3 月 2 日。要分得出
    「冇寫」同「寫錯咗」,因為兩者要改嘅嘢唔同。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-02-30'}})")
    assert got["due"] is None
    assert got["dueReason"] == "due-unusable"


def test_an_absurd_year_is_unusable(page, server):
    """due:2926-09-18 打錯年份 — 一放落條軸就係三十幾萬個日期。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2926-09-18'}})")
    assert got["dueReason"] == "due-unusable"


def test_a_due_on_the_start_day_cannot_carry_a_line(page, server):
    """啱啱等於起點:個日期畫得出,但拉唔出一條線 — 第三個原因。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-08-01'}})")
    assert got["due"] == "2026-08-01"
    assert got["dueReason"] == "due-not-after-start"


def test_a_due_before_the_start_is_the_same_reason(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-07-01'}})")
    assert got["dueReason"] == "due-not-after-start"


def test_real_date_rejects_the_shapes_that_parse_but_do_not_exist(page, server):
    got = evaluate(page, server,
                   "[m.realDate('2026-08-04'), m.realDate('2026-02-30'), "
                   "m.realDate('2026-13-01')]")
    assert got == [True, False, False]


def test_span_days_is_inclusive(page, server):
    got = evaluate(page, server, "m.spanDays('2026-08-01', '2026-08-04')")
    assert got == 4
