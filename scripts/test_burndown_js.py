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
    """今日之後嗰段係 runway,remaining 同 scope 都唔應該再有數 ——
    唔係「剩返零」,亦唔係「範圍已知」。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["todayIndex"] == 3
    assert got["remaining"][4:] == [None] * (len(got["days"]) - 4)
    assert got["scope"][4:] == [None] * (len(got["days"]) - 4)


def test_the_ideal_line_reaches_zero_on_the_due_date(page, server):
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["days"][-1] == "2026-08-06"
    assert got["ideal"][0] == 10
    assert got["ideal"][-1] == 0


def test_the_ideal_line_anchors_to_starting_scope_not_starting_remaining(page, server):
    """起點嗰日已經做咗啲嘢,remaining(6) 同 total(10) 唔同,先分得出
    理想線錨喺邊個 —— 錨喺 total,唔係 total - done。"""
    plan = """{
      path: 'plan.md', done: 4, total: 10, due_max: '2026-08-03',
      history_truncated: false,
      history: [
        {date: '2026-08-01', done: 4, total: 10},
        {date: '2026-08-02', done: 6, total: 10},
      ],
    }"""
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-02')")
    assert got["ideal"][0] == 10


def test_no_due_date_means_no_ideal_line(page, server):
    """冇 due: 就唔可以作一條死線出嚟 — 剩餘同 scope 照出。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: null")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["due"] is None
    assert all(v is None for v in got["ideal"])
    assert got["remaining"][0] == 10


def test_a_drawable_ideal_line_carries_no_reason(page, server):
    """有線就唔應該有藉口 —— 一個永遠出 reason 嘅實作會令下面每個
    「講得出點解」嘅測試都照樣綠,但每張健康嘅卡都會多一句廢話。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["idealReason"] is None


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-08-32", "2026-02-30"])
def test_a_calendar_invalid_due_draws_no_line_and_keeps_the_chart(page, server, bad):
    """`due:` 淨係驗過個 shape,冇驗過個日曆 —— `2026-13-01` 喺字串大細度
    贏晒同年所有真日期,然後喺前端變 NaN:條軸變空,張卡剩返一格白。

    `2026-02-30` 更加賤:JS 唔會出 NaN,佢會靜靜哋碌去 3 月 2 日,喺條軸
    上面點都揾唔到,結果係一條冇解釋嘅冇線。三個都要當「唔係有效日期」,
    而剩餘 / scope 兩條線要照出 —— 一個打錯咗嘅死線唔應該食埋成張卡。"""
    plan = PLAN.replace("due_max: '2026-08-06'", f"due_max: '{bad}'")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["idealReason"] == "due-unusable"
    assert got["due"] is None
    assert all(v is None for v in got["ideal"])
    assert got["days"] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]
    assert got["remaining"][:4] == [10, 10, 9, 9]


def test_a_far_future_due_never_builds_a_giant_axis(page, server):
    """`due:2926-09-18`(打錯咗個年份)= 328,767 日 × 3 條 dataset 交去
    Chart.js 喺 main thread 度畫 —— 死嘅唔止呢張卡,係成個 dashboard。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: '2926-09-18'")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert len(got["days"]) == 4          # 條軸淨係跟真實觀測,冇跟嗰個死線
    assert got["idealReason"] == "due-unusable"


def test_a_due_before_the_first_observation_says_why_there_is_no_line(page, server):
    """Heading 級 due: 就算早過所有 task due 都照贏(呢個係設計),所以一份
    喺死線之後先開檔嘅補救計劃,一開波就係呢個 case。畫唔到線唔出奇,
    但一定要講得出係邊個原因 —— 同「plan.md 冇寫 due:」唔係同一件事。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: '2026-07-01'")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["idealReason"] == "due-not-after-start"
    assert all(v is None for v in got["ideal"])
    assert got["remaining"][:2] == [10, 10]   # 其餘兩條線照出


def test_a_due_equal_to_the_first_observation_says_why_there_is_no_line(page, server):
    """啱啱等於第一個觀測:`dueIndex === 0`,除數係零,一樣拉唔出線。
    邊界要同「早過」行同一條路,唔可以靜靜哋畫一條全 null 又冇交代。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: '2026-08-01'")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["idealReason"] == "due-not-after-start"
    assert all(v is None for v in got["ideal"])


def test_a_missing_due_is_told_apart_from_an_unplottable_one(page, server):
    """兩者都係「冇理想線」,但要改嘅嘢完全唔同:一個係去 plan.md 加
    `due:`,另一個係佢已經有,只不過寫錯咗 / 太早。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: null")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["idealReason"] == "no-due"


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
