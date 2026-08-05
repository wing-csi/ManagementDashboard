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
    assert got == {"start": "2026-08-01", "startSource": "observation",
                   "startReason": None, "due": "2026-09-18", "dueReason": None}


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


# ---------------------------------------------------- 起點嘅三層 fallback

FULL = HIST + ", start_min: '2026-06-16', repo_first_commit: '2026-05-03'"


def test_a_declared_start_wins_over_the_repo_and_the_observation(page, server):
    got = evaluate(page, server, f"m.resolvePlanWindow({{{FULL}}})")
    assert got["start"] == "2026-06-16"
    assert got["startSource"] == "plan"
    assert got["startReason"] is None


def test_without_a_declared_start_the_repo_first_commit_is_used(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, repo_first_commit: '2026-05-03'}})")
    assert got["start"] == "2026-05-03"
    assert got["startSource"] == "repo"
    assert got["startReason"] is None


def test_an_old_metrics_json_still_starts_at_the_first_observation(page, server):
    """兩個 key 都冇 = 舊數據。行為要同呢個 feature 之前一模一樣。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] is None


def test_a_start_that_is_not_a_calendar_date_falls_through_and_says_so(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, start_min: '2026-02-30', "
                   f"repo_first_commit: '2026-05-03'}})")
    assert got["start"] == "2026-05-03"
    assert got["startSource"] == "repo"
    assert got["startReason"] == "start-unusable"


def test_a_month_thirteen_start_is_unusable_not_late(page, server):
    """`'2026-13-01' > '2026-08-01'` 係字串比大細,答「係」,但佢唔係遲咗 ——
    佢根本唔係一個日期。揀錯咗個 reason,張卡就會叫人去改一個唔存在嘅問題。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, start_min: '2026-13-01'}})")
    assert got["startReason"] == "start-unusable"


def test_a_start_far_enough_back_to_blow_the_axis_is_unusable_too(page, server):
    """`realDate('1900-01-01')` 係真,但 dayRange() 會生四萬幾個日期,而佢個
    cap 係剪尾 —— 剪走今日同死線。同 due-unusable 一樣一句過。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, start_min: '1900-01-01'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] == "start-unusable"


def test_a_start_later_than_the_first_observation_is_not_believed(page, server):
    """plan.md 話八月三號開始,但 git 話八月一號已經 commit 過呢份 plan。
    採用佢就要切走一個真係量度過嘅觀測點,而個圖會睇落完全正常。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, start_min: '2026-08-03'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] == "start-after-history"


def test_a_bad_repo_first_commit_is_dropped_without_a_reason(page, server):
    """`repo_first_commit` 唔係人手寫嘅 —— 出一句叫人去改乜嘢都冇。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, repo_first_commit: '2026-13-01'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] is None


def test_the_due_gate_measures_from_the_resolved_start(page, server):
    """MAX_DAYS 個 due 閘由 start 起計 —— 起點推早咗,個閘要跟住郁。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{FULL}, due_max: '2026-09-18'}})")
    assert got["start"] == "2026-06-16"
    assert got["due"] == "2026-09-18"
    assert got["dueReason"] is None


def test_due_not_after_start_now_measures_against_the_resolved_start(page, server):
    """起點推早咗,一個以前「唔遲過起點」嘅 due 而家遲過佢 —— 拉得出線。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, repo_first_commit: '2026-05-03', "
                   f"due_max: '2026-07-01'}})")
    assert got["dueReason"] is None


def test_a_plan_with_no_history_has_no_start_source(page, server):
    got = evaluate(page, server, "m.resolvePlanWindow({history: []})")
    assert got["start"] is None
    assert got["startSource"] is None
    assert got["startReason"] is None
    assert got["dueReason"] == "no-history"
