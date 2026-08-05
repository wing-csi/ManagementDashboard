"""Plan timeline 條嘅渲染守則。

同 burndown 卡一樣嘅規矩:冇畫嘅嘢一定要講得出點解。條線最容易靜靜哋
出錯嘅地方係空狀態 —— 每一個都要有自己嘅講法,唔可以共用一句,亦唔可以
留一格白。

Run:  python -m pytest scripts/test_frontend_timeline.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="timeline rendering tests need pytest-playwright")

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


def test_the_strip_renders_one_marker_per_distinct_due(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark",
                                     "els => els.length") == 3


def test_overdue_markers_are_marked_overdue(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark.tl-overdue",
                                     "els => els.length") == 1


def test_the_header_reports_spi_days_left_and_overdue_count(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-head", state="attached")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0.42" in head      # 3/12 done ÷ 3/5 elapsed
    assert "嚴重落後" in head
    assert "剩 2 日" in head
    assert "2 個 task 過咗期" in head


def test_a_marker_carries_its_tasks_in_the_tooltip(page, server):
    """兩個 task 迫埋同一日 — tooltip 要列晒,唔可以淨係講一個。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    tip = dash.eval_on_selector("#burndownCards .tl-mark",
                                "el => el.getAttribute('title')")
    assert "P-01" in tip and "P-02" in tip
    assert "P1" in tip


def test_today_is_marked_on_the_strip(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-today", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-today",
                                     "els => els.length") == 1


def test_the_strip_always_says_it_only_shows_unfinished_work(page, server):
    """條線只畫未打勾嘅 task。唔講嘅話,做完嘢令條線變疏會被讀成「順利」。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "未做" in dash.inner_text("#burndownCards .tl")


def test_an_unusable_due_says_so_and_shows_no_spi(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-02-30"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "唔係一個有效日期" in text
    # 唔可以斷言「冇 SPI 呢三個字」—— 解釋嗰句本身就有「冇 SPI」。要斷言嘅
    # 係冇一個 SPI **數字**,亦冇任何一個 band 判斷。
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0." not in head
    assert not any(band in head for band in ("追得上", "落後", "嚴重落後"))


def test_a_plan_with_no_task_dues_says_so(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["open_tasks"] = []
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "冇寫 due:" in dash.inner_text("#burndownCards .tl")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark",
                                     "els => els.length") == 0


def test_a_finished_plan_says_nothing_is_left_not_no_dates(page, server):
    """「冇嘢剩低」同「冇寫 due:」兩個都係零粒 marker,唔可以共用一句。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan["open_tasks"] = []
    plan["done"] = plan["total"]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "冇嘢剩低" in text
    assert "冇寫 due:" not in text


def test_invalid_task_dues_are_counted_in_the_note(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["open_tasks"].append(
        {"title": "P-99 壞日期", "due": "2026-02-30", "priority": "P2",
         "bug": False, "section": "Phase 2"})
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "1 個" in dash.inner_text("#burndownCards .tl")


def test_a_failed_history_fetch_draws_no_strip_at_all(page, server):
    """Burndown 已經出咗聲,條線唔好再嘈一次 —— 亦唔可以扮有數據。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["history"]
    plan["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .burndown-card", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl", "els => els.length") == 0


def test_old_metrics_without_plan_history_render_no_strip(page, server):
    data = _load()
    for meta in data["repo_meta"].values():
        meta.pop("plan", None)
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0
