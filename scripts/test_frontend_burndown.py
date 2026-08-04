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


def test_old_metrics_without_any_plan_history_hide_the_section(page, server):
    """向後兼容:舊 metrics.json 兩個 key 都冇,成個 section 收埋,唔係報錯,
    亦唔會當佢係「讀唔到」而出一張錯嘅卡。"""
    data = _load()
    for meta in data["repo_meta"].values():
        meta.pop("plan", None)
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0


def test_today_is_marked_on_the_chart(page, server):
    """今日條線係「追唔追得上」嘅參考點 —— 冇佢,兩條線嘅開叉讀唔出意思。"""
    data = _load()
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    drawn = dash.evaluate(
        "() => Chart.getChart(document.querySelector('#burndownCards canvas'))"
        ".options.plugins.todayMarker.index")
    assert drawn == 3  # fixture: 2026-08-01 起,今日 2026-08-04
