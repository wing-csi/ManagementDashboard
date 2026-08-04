"""Unit tests for docs/js/burndown.js, executed in a real browser.

Same approach as test_aggregate_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

Run:  python -m pytest scripts/test_burndown_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="burndown.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/burndown.js'); "
        f"return ({body}); }}"
    )


PLAN = """{
  path: 'plan.md', done: 3, total: 12, due_max: '2026-08-06',
  history_truncated: false,
  history: [
    {date: '2026-08-01', done: 0, total: 10},
    {date: '2026-08-03', done: 3, total: 12},
  ],
}"""


def test_remaining_carries_forward_between_observations(page, server):
    """Plan 冇改過嗰啲日唔係冇數 — 係同前一日一樣。收集端只出真實觀測,
    填平嗰段係前端嘅事。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["days"][:4] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]
    assert got["remaining"][:4] == [10, 10, 9, 9]
    assert got["scope"][:4] == [10, 10, 12, 12]


def test_the_actual_line_stops_at_today(page, server):
    """今日之後嗰段係 runway,唔係「剩返零」。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["todayIndex"] == 3
    assert got["remaining"][4:] == [None] * (len(got["days"]) - 4)


def test_the_ideal_line_reaches_zero_on_the_due_date(page, server):
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["days"][-1] == "2026-08-06"
    assert got["ideal"][0] == 10
    assert got["ideal"][-1] == 0


def test_no_due_date_means_no_ideal_line(page, server):
    """冇 due: 就唔可以作一條死線出嚟 — 剩餘同 scope 照出。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: null")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["due"] is None
    assert all(v is None for v in got["ideal"])
    assert got["remaining"][0] == 10


def test_the_axis_still_reaches_today_when_the_due_date_has_passed(page, server):
    """遲咗嘅項目一樣要見到今日,否則個圖會喺死線度斷。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-20')")
    assert got["days"][-1] == "2026-08-20"


def test_a_single_observation_is_flagged_not_drawn_as_a_trend(page, server):
    plan = """{path: 'plan.md', done: 0, total: 5, due_max: '2026-09-01',
               history_truncated: false,
               history: [{date: '2026-08-01', done: 0, total: 5}]}"""
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["status"] == "single-point"


def test_a_missing_history_key_is_not_an_empty_chart(page, server):
    plan = "{path: 'plan.md', done: 3, total: 12, due_max: '2026-09-01'}"
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["status"] == "no-history"
