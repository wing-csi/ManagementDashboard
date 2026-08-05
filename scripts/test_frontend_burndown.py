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


def test_the_card_leads_with_the_five_pm_decision_metrics(page, server):
    """PM 唔應該由三條線自己心算進度差距、scope 同目標日。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    text = dash.inner_text("#burndownCards")
    assert "落後計劃" in text
    assert "實際進度比今日計劃落後 35 個百分點" in text
    metrics = dash.locator("#burndownCards .burn-metric").evaluate_all(
        "els => els.map(el => el.textContent.replace(/\\s+/g, ' ').trim())")
    assert "完成進度 25% 3 / 12 已完成" in metrics
    assert "剩餘工作 9 項未完成" in metrics
    assert "目標日 08/06 剩 2 日" in metrics
    assert "範圍變動 +2 起點 10 → 現在 12" in metrics
    assert "預測完成 — 需要最少 7 日歷史" in metrics


def test_the_card_names_freshness_source_and_keeps_task_dates_on_demand(page, server):
    """趨勢同 task deadline 分層:來源/freshness 常駐,逐項期限按需要展開。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .burn-task-details", state="attached")
    text = dash.inner_text("#burndownCards")
    assert "數據截至 2026-08-04 · 每日 05:00 HKT 更新" in text
    assert "來源：plan.md commit 歷史" in text
    details = dash.locator("#burndownCards .burn-task-details")
    assert details.evaluate("el => el.open") is False
    assert "查看 4 項未完成工作的期限" in details.locator("summary").inner_text()


def test_backfilled_history_is_drawn_but_names_its_provenance_and_scope_limit(page, server):
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan["history"][0]["source"] = "task-date"
    plan["history"][1]["source"] = "snapshot"
    plan.update(history_backfilled=True, history_backfill_tasks=3,
                history_backfill_coverage=1.0,
                history_source="task-dates+plan-commits")
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    text = dash.inner_text("#burndownCards")
    assert "來源：plan.md task done: 日期 + commit 歷史" in text
    assert "完成趨勢由 3 項 task done: 日期回填（覆蓋 100%）" in text
    assert "scope 變動只計真實 plan snapshot" in text
    scope_metric = dash.locator("#burndownCards .burn-metric").nth(3).evaluate(
        "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    assert scope_metric == "範圍變動 0 由 08/03 起 12 → 現在 12"
    scope_data = dash.eval_on_selector(
        "#burndownCards canvas",
        "el => Chart.getChart(el).data.datasets[1].data.slice(0, 4)",
    )
    assert scope_data == [None, None, 12, 12]


def test_observed_remaining_and_scope_are_steps_not_invented_daily_slopes(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    chart_options = dash.eval_on_selector(
        "#burndownCards canvas",
        "el => Chart.getChart(el).data.datasets.map(d => d.stepped || false)",
    )
    assert chart_options[:2] == ["before", "before"]
    assert chart_options[2] is False  # 理想線先至係連續斜線


def test_a_guarded_completion_forecast_is_visible_and_compared_with_target(page, server):
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan.update(done=4, total=10, due_max="2026-08-10")
    plan["history"] = [
        {"date": "2026-07-20", "done": 0, "total": 10},
        {"date": "2026-07-27", "done": 2, "total": 10},
        {"date": "2026-08-03", "done": 4, "total": 10},
    ]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    metric = dash.locator("#burndownCards .burn-metric").last.evaluate(
        "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    assert metric.startswith("預測完成 08/27")
    assert "中信心" in metric
    assert "遲 17 日" in metric


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
    dash.wait_for_selector("#burndownCards .burn-chart-empty", state="attached")
    assert dash.eval_on_selector_all("#burndownCards canvas", "els => els.length") == 0
    text = dash.inner_text("#burndownCards")
    assert "未有足夠觀測畫趨勢" in text
    assert "未成趨勢" in text


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


# ------------------------------------------------------ 條軸個起點邊度嚟

def _card_text(page, server, data: dict) -> str:
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    return dash.inner_text("#burndownCards")


def _with_repo_start(date: str = "2026-07-20") -> dict:
    """Fixture 個 `repo_first_commit` 係 null —— 條軸由第一個觀測起,
    今日線同 SPI 嗰批 test 先至唔使跟住起點嘅來源郁。要 C 層嘅 test
    自己注入。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["repo_first_commit"] = date
    return data


def test_the_card_names_where_the_start_came_from(page, server):
    """同一條軸,由 repo 開檔拉起同由第一次改 plan.md 拉起,理想線同 SPI
    嘅意思完全唔同,但畫面上一模一樣 —— 唔講就分唔到。"""
    assert "起點:repo 第一個 commit" in _card_text(page, server, _with_repo_start())


def test_a_declared_start_is_named_as_such(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-06-16"
    assert "起點:plan.md start:" in _card_text(page, server, data)


def test_an_old_metrics_json_names_the_first_plan_commit(page, server):
    """兩個 key 都冇 = 舊數據。出處要講返係第三層,唔可以扮成宣告過。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["start_min"]
    del plan["repo_first_commit"]
    assert "起點:第一次改 plan.md" in _card_text(page, server, data)


def test_an_unusable_declared_start_says_what_to_fix(page, server):
    data = _with_repo_start()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-02-30"
    text = _card_text(page, server, data)
    assert "plan.md 個 start: 唔係一個畫得出嘅日期" in text
    assert "起點:repo 第一個 commit" in text     # 同時要講跌咗去邊


def test_a_late_declared_start_says_it_was_not_believed(page, server):
    """宣告嘅起點遲過第一個觀測 = 同 git 記錄矛盾。唔採用,但要出聲。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-08-03"
    assert "start: 遲過第一個觀測,冇採用" in _card_text(page, server, data)


def test_the_truncated_caption_only_speaks_when_the_start_is_an_observation(page, server):
    """歷史截斷咗但起點由 repo 開檔話事嘅時候,理想線**唔係**由「現存最早
    嗰個觀測」起計 —— 照出嗰句就係講錯嘢。"""
    data = _with_repo_start()
    data["repo_meta"]["acme/alpha"]["plan"]["history_truncated"] = True
    assert "已截斷" not in _card_text(page, server, data)


def test_the_truncated_caption_still_speaks_on_an_old_metrics_json(page, server):
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan["history_truncated"] = True
    del plan["start_min"]
    del plan["repo_first_commit"]
    assert "已截斷" in _card_text(page, server, data)
