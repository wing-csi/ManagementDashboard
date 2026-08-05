"""Unit tests for docs/js/timeline.js, executed in a real browser.

Same approach as test_burndown_js.py. The two things most likely to go wrong
silently are covered hardest: a marker falling outside the axis (drawn
nowhere, explained nowhere), and SPI dividing by a zero-length elapsed window
(rendering Infinity or NaN as if it were a measurement).

Run:  python -m pytest scripts/test_timeline_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="timeline.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/timeline.js'); "
        f"return ({body}); }}"
    )


PLAN = """{
  path: 'plan.md', done: 3, total: 12, due_max: '2026-08-06',
  history: [
    {date: '2026-08-01', done: 0, total: 10},
    {date: '2026-08-03', done: 3, total: 12},
  ],
  open_tasks: [
    {title: 'P-01', due: '2026-08-01', priority: 'P1', bug: true},
    {title: 'P-02', due: '2026-08-01', priority: 'P2', bug: false},
    {title: 'P-03', due: '2026-08-06', priority: 'P1', bug: false},
    {title: 'P-04', due: '2026-08-20', priority: 'P2', bug: false},
  ],
}"""


def test_the_axis_stretches_past_due_max_to_cover_a_later_task(page, server):
    """一個遲過 due_max 嘅 task 一樣係真嘢。軸唔撐開,嗰粒就跌出畫面 ——
    冇畫,又冇講,正正係 514608b 修過嗰種錯。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["axisStart"] == "2026-08-01"
    assert got["axisEnd"] == "2026-08-20"


def test_the_axis_stretches_back_for_a_task_due_before_the_plan_started(page, server):
    plan = PLAN.replace("{title: 'P-04', due: '2026-08-20'",
                        "{title: 'P-04', due: '2026-07-20'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["axisStart"] == "2026-07-20"


def test_tasks_sharing_a_date_become_one_marker(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    first = got["markers"][0]
    assert first["date"] == "2026-08-01"
    assert first["count"] == 2
    assert [t["title"] for t in first["tasks"]] == ["P-01", "P-02"]


def test_overdue_counts_tasks_not_markers(page, server):
    """兩個 task 迫喺同一日,係兩個過期,唔係一個。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["overdue"] == 2


def test_markers_are_classified_by_distance_from_today(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert [m["urgency"] for m in got["markers"]] == ["overdue", "soon7", "later"]


def test_the_bar_spans_the_declared_window_not_the_axis(page, server):
    """條 bar 係「計劃咗幾耐」,條軸係「要畫幾闊」。撈埋一齊嘅話,
    一個遲 task 就會令個項目睇落計劃到 8 月 20 號。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["barLeftPct"] == 0
    # 08-01..08-06 係 20 日軸(08-01..08-20)入面嘅頭 6 日
    assert round(got["barWidthPct"]) == 26


def test_spi_divides_progress_by_elapsed_time(page, server):
    """3/12 做完,而 08-01→08-06 走咗 3/5。0.25 / 0.6 = 0.42。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["spi"] == 0.42
    assert got["spiReason"] is None


def test_spi_is_absent_before_the_plan_starts(page, server):
    """今日 == 起點:elapsed 係 0,除唔到。要出「未開始」,唔可以出 Infinity。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-01')")
    assert got["spi"] is None
    assert got["spiReason"] == "not-started"


def test_spi_is_absent_when_the_due_is_unusable(page, server):
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: '2026-02-30'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["spi"] is None
    assert got["spiReason"] == "due-unusable"
    assert got["daysLeft"] is None


def test_a_zero_task_plan_is_not_behind_schedule(page, server):
    """0/0 係 NaN,而 NaN 輸晒所有比較,最後會靜靜哋顯示做「嚴重落後」。
    冇 task 唔係落後。"""
    plan = PLAN.replace("done: 3, total: 12", "done: 0, total: 0")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["spi"] is None
    assert got["spiReason"] == "no-tasks"


def test_days_left_counts_from_today_to_the_due(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["daysLeft"] == 2


def test_days_left_goes_negative_once_the_due_has_passed(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-10')")
    assert got["daysLeft"] == -4


def test_a_calendar_invalid_task_due_is_dropped_and_counted(page, server):
    """靜靜哋掉咗會令「過期」個數虛低 —— 數低咗先講得出。"""
    plan = PLAN.replace("{title: 'P-04', due: '2026-08-20'",
                        "{title: 'P-04', due: '2026-02-30'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["invalidDues"] == 1
    assert all(mk["date"] != "2026-02-30" for mk in got["markers"])


def test_a_plan_with_no_dated_tasks_still_has_a_bar(page, server):
    plan = PLAN.replace(PLAN[PLAN.index("open_tasks"):PLAN.rindex("],") + 2],
                        "open_tasks: []")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["markers"] == []
    assert got["axisEnd"] == "2026-08-06"


def test_all_tasks_ticked_is_flagged_separately(page, server):
    """「冇嘢剩低」同「冇寫 due:」兩個都係零粒 marker,但意思啱啱相反。"""
    plan = PLAN.replace("done: 3, total: 12", "done: 12, total: 12")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["allDone"] is True


def test_no_history_reports_no_history(page, server):
    got = evaluate(page, server,
                   "m.timelineStrip({path: 'plan.md', done: 1, total: 2}, '2026-08-04')")
    assert got["status"] == "no-history"
    assert got["markers"] == []


# ------------------------------------------------ SPI 跟解析咗嘅起點,唔係觀測

SPI_PLAN = ("{done: 3, total: 12, due_max: '2026-09-01', open_tasks: [], "
            "repo_first_commit: '2026-07-01', "
            "history: [{date: '2026-08-01', done: 0, total: 10}]}")


def test_spi_measures_from_the_resolved_start(page, server):
    """SPI 個分母係計劃窗口,唔係「我哋幾時開始有記錄」。錨返第一個觀測
    會令一個做咗三個月、上星期先開 plan.md 嘅項目報一個近乎完美嘅 SPI。"""
    got = evaluate(page, server, f"m.timelineStrip({SPI_PLAN}, '2026-08-16')")
    # elapsed = (08-16 − 07-01) / (09-01 − 07-01) = 46/62 = 0.7419…
    # SPI = (3/12) / 0.7419… = 0.34;錨返 08-01 嘅話會係 0.5
    assert got["start"] == "2026-07-01"
    assert got["startSource"] == "repo"
    assert got["spi"] == 0.34


def test_the_bar_starts_at_the_resolved_start(page, server):
    got = evaluate(page, server, f"m.timelineStrip({SPI_PLAN}, '2026-08-16')")
    assert got["axisStart"] == "2026-07-01"
    assert got["barLeftPct"] == 0
