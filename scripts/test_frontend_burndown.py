"""項目 burndown 卡嘅渲染守則。

每個空狀態都要各有講法:冇圖嘅時候一定要講得出點解,唔可以留一格白,
亦唔可以畫一條假線。呢個係成張卡最容易靜靜哋出錯嘅地方。

Run:  python -m pytest scripts/test_frontend_burndown.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="burndown rendering tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-burndown.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def _open(page, server):
    page.goto(f"{server}/", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def test_a_repo_with_plan_history_gets_a_chart(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert dash.eval_on_selector_all("#burndownCards canvas", "els => els.length") == 1
    # A healthy plan (due set, 2 history points, not truncated) must not carry
    # any of the caveat captions — a captionFor() that emitted them
    # unconditionally would still pass every other test in this file.
    text = dash.inner_text("#burndownCards")
    assert "未成趨勢" not in text
    assert "冇理想線" not in text
    assert "已截斷" not in text


def test_a_failed_history_fetch_says_so_instead_of_drawing_a_flat_line(page, server):
    """讀唔到就要出聲。一條平線同一張消失咗嘅卡都係當「冇嘢做緊」,兩個都呃人。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["history"]
    plan["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .burndown-card", state="attached")
    assert dash.eval_on_selector_all("#burndownCards canvas", "els => els.length") == 0
    assert "攞唔到" in dash.inner_text("#burndownCards")


def test_a_plan_without_a_due_date_says_why_there_is_no_ideal_line(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = None
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "冇理想線" in dash.inner_text("#burndownCards")


def test_a_single_observation_says_it_is_not_a_trend_yet(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["history"] = [
        {"date": "2026-08-01", "done": 0, "total": 10}]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "未成趨勢" in dash.inner_text("#burndownCards")


def test_a_truncated_history_says_the_ideal_line_moved(page, server):
    """截斷掉走最舊嗰批,理想線就唔再由項目開頭拉出嚟 — 唔講嘅話條線係呃人。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["history_truncated"] = True
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "已截斷" in dash.inner_text("#burndownCards")


def test_old_metrics_with_a_plan_but_no_history_hide_the_section(page, server):
    """向後兼容:舊 metrics.json 兩個 key 都冇,成個 section 收埋,唔係報錯,
    亦唔會當佢係「讀唔到」而出一張錯嘅卡。

    `plan` 一定要留喺度。`fetch_plan_file` 早過呢個 feature,所以真實嘅
    pre-feature 數據個 `plan` 係齊嘅(done/total/path/ref/sections/open_tasks),
    淨係少咗 `history` 同 `history_error`。用 `meta.pop("plan")` 做 fixture 嘅話,
    條 guard 嘅 `!plan` 一 short-circuit,第二半就永遠冇行過 —— 咁樣將條
    guard 簡化成 `if (!plan) continue;` 都會全綠,但每一個舊 dashboard 都會
    當「有 plan 冇歷史」= 有嘢畫,出一張空卡。"""
    data = _load()
    for meta in data["repo_meta"].values():
        plan = meta.get("plan")
        if plan:
            plan.pop("history", None)
            plan.pop("history_error", None)
    assert data["repo_meta"]["acme/alpha"]["plan"]["total"] == 12  # 個 plan 仲喺度
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0


def test_a_repo_with_no_plan_file_at_all_hides_the_section(page, server):
    """冇設 `plan_file` 嘅 repo 連 `plan` key 都冇 —— 另一半條 guard。"""
    data = _load()
    for meta in data["repo_meta"].values():
        meta.pop("plan", None)
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0


def test_a_due_date_that_cannot_be_plotted_still_explains_itself(page, server):
    """宣告咗但畫唔出嘅死線(早過第一個觀測)以前係「冇線又冇解釋」——
    `captionFor()` 淨係問 `!series.due`,而呢種 case 個 due 係有值嘅。
    Heading 級 due: 早過所有 task due 都照贏係本 branch 嘅設計,所以一份
    喺死線之後先開檔嘅補救計劃一開波就撞正呢個位。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-07-01"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    text = dash.inner_text("#burndownCards")
    assert "拉唔出理想線" in text
    # 同「plan.md 冇 due:」要分得開 —— 兩者要改嘅嘢唔同。
    assert "冇 due:" not in text


def test_a_calendar_invalid_due_date_says_so_instead_of_going_blank(page, server):
    """舊 metrics.json 入面個 `due_max` 冇驗過日曆。`2026-13-01` 喺前端係
    NaN,以前會出一張有標題、有一格白圖、乜都冇講嘅卡。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-13-01"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "唔係一個有效日期" in dash.inner_text("#burndownCards")


def test_today_is_marked_on_the_chart(page, server):
    """今日條線係「追唔追得上」嘅參考點 —— 冇佢,兩條線嘅開叉讀唔出意思。

    讀 `.options.plugins.todayMarker.index` 唔夠:嗰個淨係一個 config
    namespace,`new Chart(...)` 漏咗 `plugins: [todayMarker]` 都照樣有得讀,
    但條線根本冇畫過。改為讀 `$todayMarkerDrawnIndex` —— 呢個係個 plugin
    嘅 `afterDatasetsDraw` hook 真係行過先會寫低嘅痕跡,證明個 plugin 有
    掛牢喺呢個 chart 度,唔淨係設定存在。"""
    data = _load()
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    # #burndownCards lives inside the Projects tab panel, which starts hidden
    # (display: none — see docs/js/tabs.js). Chart.js constructs the chart
    # against a 0x0 canvas there and only performs its real draw once the
    # panel becomes visible and its ResizeObserver reports a real size, same
    # as any real user has to click into the tab to see this card at all.
    dash.click("#tab-projects")
    # The resize-triggered redraw can land a frame after the click, so poll
    # for the drawn side effect rather than reading it synchronously.
    # fixture: history starts 2026-08-01, today is 2026-08-04 → index 3.
    dash.wait_for_function(
        "() => Chart.getChart(document.querySelector('#burndownCards canvas'))"
        "?.$todayMarkerDrawnIndex === 3")


def test_a_chart_rebuilt_while_its_tab_is_hidden_still_renders_once_shown(page, server):
    """真實流程:用戶一開始留喺 Overview(default tab),Projects panel 收埋
    (display:none)。呢個時候揀第個 filter,`render()` 會重新整個
    `renderBurndown()`,charts Map 攞住一個 0x0 嘅 canvas 起 Chart —— 跟住
    先至切去 Projects tab。要證明條 chart 唔會停喺嗰個 0x0 嘅一刻,冇畫過
    就算數。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert dash.evaluate("document.getElementById('panel-projects').hidden") is True

    # 重新 render 一次,而 Projects panel 呢陣時仲係隱藏緊 —— 呢個先係
    # coordinator 講嗰個 path,唔係一開波就切去 Projects 嗰種。
    dash.select_option("#windowSel", "180")
    # 用嚟證明真係喺隱藏緊嗰陣重新整過個 chart:呢一刻 canvas 應該係 0x0。
    assert dash.eval_on_selector("#burndownCards canvas", "el => el.width") == 0

    dash.click("#tab-projects")
    dash.wait_for_function(
        "() => { const c = document.querySelector('#burndownCards canvas');"
        " return c && c.width > 0; }")
    assert dash.eval_on_selector("#burndownCards canvas", "el => el.width") > 0
    dash.wait_for_function(
        "() => Chart.getChart(document.querySelector('#burndownCards canvas'))"
        "?.$todayMarkerDrawnIndex === 3")
