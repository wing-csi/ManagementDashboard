"""Tests for TRACK A (static chrome) string extraction: docs/index.html
masthead/tabs/filters/load-error/footer, the dynamic chrome built in
docs/js/main.js, and the docs/js/staleness.js banner messages.

Every dict namespace this track owns (docs/js/i18n/dict/{zh,en}/chrome.js
and .../misc.js) started life as an empty `Object.freeze({})` stub — filling
them, and wiring `data-i18n` / `data-i18n-attr` onto the markup, is the work
this test file exercises.

With no `?lang=` param the page must still render byte-for-byte identical
Chinese — that is the override-layer contract the whole i18n rollout
depends on, and it is asserted below alongside the English output.

Run:  python -m pytest scripts/test_frontend_i18n_chrome.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                     reason="i18n tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture.json"


def open_dashboard(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


# ------------------------------ default is zh ------------------------------

def test_default_lang_keeps_exact_chinese_chrome(page, server):
    """No `lang` param — the override contract: chrome text stays Chinese."""
    open_dashboard(page, server)
    assert page.title() == "AI 自動化水平儀"
    assert page.text_content("#tab-overview") == "總覽"
    assert page.text_content("#tab-quality") == "品質"
    assert page.text_content("#tab-projects") == "項目 & 團隊"
    assert page.text_content("#tab-product") == "產品 & 發佈"
    assert page.text_content("#tab-tasks") == "工作"
    assert page.get_attribute("#repoSel", "aria-label") == "程式庫"
    assert page.get_attribute("#taskSearch", "placeholder") == "搜尋標題 / 作者 / 分支 / PR"
    assert page.text_content("#demoBadge") == "示範數據 · 手動要求（?demo=1）"


# -------------------------------- ?lang=en --------------------------------

def test_title_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.title() == "AI Autonomy Gauge"


def test_five_tab_labels_are_translated_and_stay_one_word(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    expected = {
        "#tab-overview": "Overview",
        "#tab-quality": "Quality",
        "#tab-projects": "Projects",
        "#tab-product": "Product",
        "#tab-tasks": "Tasks",
    }
    for selector, text in expected.items():
        got = page.text_content(selector)
        assert got == text
        assert " " not in got, f"{selector} tab label is not one word: {got!r}"


def test_four_filter_aria_labels_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.get_attribute("#repoSel", "aria-label") == "Repository"
    assert page.get_attribute("#branchSel", "aria-label") == "Branch"
    assert page.get_attribute("#personSel", "aria-label") == "Contributor"
    assert page.get_attribute("#windowSel", "aria-label") == "Time window"


def test_demo_badge_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.text_content("#demoBadge") == "Demo data · explicitly requested (?demo=1)"


def test_window_options_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    labels = page.eval_on_selector_all(
        "#windowSel option", "els => els.map(e => e.textContent)")
    assert labels == ["Last 30 days", "Last 60 days", "Last 90 days", "Last 180 days"]


def test_task_search_placeholder_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.get_attribute("#taskSearch", "placeholder") == "Search title / author / branch / PR"


def test_load_error_block_is_translated(page, server):
    page.route("**/data/metrics.json", lambda route: route.fulfill(status=500))
    page.goto(f"{server}/?lang=en", wait_until="networkidle")
    page.wait_for_selector("#loadError", state="visible", timeout=10_000)
    text = page.text_content("#loadError")
    assert "Failed to load data." in text
    assert "Not signed in, or the session has expired?" in text
    assert "sign in again" in text
    assert "network error" in text or "(" in text


def test_load_error_unauthorized_is_translated(page, server):
    page.route("**/data/metrics.json", lambda route: route.fulfill(status=401))
    page.goto(f"{server}/?lang=en", wait_until="networkidle")
    page.wait_for_selector("#loadError", state="visible", timeout=10_000)
    assert page.text_content("#loadErrorDetail") == "Sign-in required."


def test_branch_select_disabled_title_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.get_attribute("#branchSel", "title") == "Select a single repository to filter by branch"


def test_branch_select_disabled_title_is_chinese_by_default(page, server):
    open_dashboard(page, server)
    assert page.get_attribute("#branchSel", "title") == "選擇單一程式庫後才可篩選分支"


def test_footer_source_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert "GitHub GraphQL API" in page.text_content("footer")
    assert "local view" in page.text_content("footer")


def test_a_misc_panel_heading_and_table_header_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.text_content("#panel-tasks h2") == "Recent tasks"
    assert page.text_content("#panel-tasks th:has-text('Date')") is not None
    header_texts = page.eval_on_selector_all(
        "#panel-tasks thead th", "els => els.map(e => e.textContent.trim())")
    assert "Repository" in header_texts
    assert "Title" in header_texts


# --------------------------- follow-up sweep (Track A) ---------------------------

def test_management_summary_aria_label_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.get_attribute(".management-kpis", "aria-label") == "Management summary"


def test_management_summary_aria_label_is_chinese_by_default(page, server):
    open_dashboard(page, server)
    assert page.get_attribute(".management-kpis", "aria-label") == "管理摘要"


def test_dora_strip_labels_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    labels = page.eval_on_selector_all(
        ".dora-strip .dl", "els => els.map(e => e.childNodes[0].textContent)")
    assert labels == [
        "Deployment frequency",
        "Lead time (to merge)",
        "Change failure rate",
        "MTTR (approx.)",
    ]
    # #dDeploySub and #dCfrSub are overwritten at runtime by render-kpi.js
    # (Track B, via kpi.dora.*); the two id-less .ds nodes are this track's
    # static copy and are never touched by JS.
    subs = page.eval_on_selector_all(
        ".dora-strip .ds:not(#dDeploySub):not(#dCfrSub)",
        "els => els.map(e => e.textContent)")
    assert subs == [
        "Median time from PR open to merge",
        "Median lead time for fix-type work",
    ]


def test_dora_strip_labels_are_chinese_by_default(page, server):
    open_dashboard(page, server)
    labels = page.eval_on_selector_all(
        ".dora-strip .dl", "els => els.map(e => e.childNodes[0].textContent)")
    assert labels == ["部署頻率", "前置時間（至合併）", "回退密度", "MTTR（近似）"]


def test_kpi_sub_lines_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.text_content("#kpiL3").strip() != ""  # sanity: hero card rendered
    hero_sub = page.eval_on_selector(".kpis .hero .hero-foot .sub", "el => el.textContent")
    assert hero_sub == "Share of work led primarily by AI agents"
    loc_sub = page.eval_on_selector(
        "#kpiLoc", "el => el.closest('.card').querySelector('.sub').textContent")
    assert loc_sub == "Share of inserted lines from L2+ work"


def test_the_two_h3_headings_are_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.text_content("#planAssignmentTitle") == "Plan task assignment"
    assert page.text_content("#defectFixTitle") == "Defect fix distribution"


def test_the_two_h3_headings_are_chinese_by_default(page, server):
    open_dashboard(page, server)
    assert page.text_content("#planAssignmentTitle") == "Plan 工作分配"
    assert page.text_content("#defectFixTitle") == "Defect 修復分佈"


def test_load_more_button_is_translated(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    assert page.text_content("#tableMore") == "Load more"


def test_load_more_button_is_chinese_by_default(page, server):
    open_dashboard(page, server)
    assert page.text_content("#tableMore") == "載入更多"


# ------------------------------ staleness.js ------------------------------

def _ago(**kw) -> str:
    stamp = datetime.now(timezone.utc) - timedelta(**kw)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve_stale(page, days: int) -> None:
    data = _load_fixture()
    data["generated_at"] = _ago(days=days)
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def test_stale_banner_interpolates_day_count_in_chinese(page, server):
    _serve_stale(page, 5)
    page.goto(f"{server}/", wait_until="networkidle")
    page.wait_for_selector("#staleBanner", state="visible")
    text = page.inner_text("#staleBanner")
    assert "5 日前" in text


def test_stale_banner_interpolates_day_count_in_english(page, server):
    _serve_stale(page, 5)
    page.goto(f"{server}/?lang=en", wait_until="networkidle")
    page.wait_for_selector("#staleBanner", state="visible")
    text = page.inner_text("#staleBanner")
    assert "5" in text
    assert "day" in text.lower()
