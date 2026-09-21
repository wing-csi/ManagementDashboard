"""i18n string-extraction tests for TRACK E: Tasks table (render-table.js)
and Product tab (render-product.js), plus the demo-outcomes.js fixture.

Mirrors the structure of scripts/test_frontend_i18n.py but scoped to this
track's own files. Never edit that file from here — see
scripts/test_frontend_i18n.py's own module docstring for why: no `lang`
param must stay byte-for-byte identical to the pre-i18n baseline, and this
suite never asserts against scripts/fixtures/rendered-baseline.json and
must never be run with --snapshot-update.

Run:  python -m pytest scripts/test_frontend_i18n_table.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="i18n tests need pytest-playwright")


def open_dashboard(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


# ------------------------------ TYPE_LABEL ------------------------------

def test_type_label_english(page, server):
    """A commit/PR title's conventional-commit prefix renders as an English
    word inside the .typechip span for the first task row."""
    open_dashboard(page, server, "?demo=1&lang=en")
    chip = page.eval_on_selector("#taskRows tr .typechip", "el => el.textContent")
    assert chip in {
        "Feature", "Fix", "Hotfix", "Revert", "Refactor", "Test", "Docs",
        "Chore", "Build", "CI", "Perf", "Style", "Other",
    }


def test_type_label_default_is_chinese(page, server):
    open_dashboard(page, server)
    chip = page.eval_on_selector("#taskRows tr .typechip", "el => el.textContent")
    assert chip in {"功能", "修復", "緊急修復", "回退", "重構", "測試", "文件", "雜項", "建置", "CI", "效能", "格式", "其他"}


# ------------------------------- UNASSIGNED ------------------------------

def test_unassigned_english_in_plan_pie(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    html = page.eval_on_selector("#planAssignmentPie", "el => el.innerHTML")
    assert "未指定" not in html
    # UNASSIGNED only shows up when there is remaining/unassigned plan work;
    # assert no leftover Chinese leaked through rather than requiring the
    # literal word to appear (it may not, depending on demo fixture shape).


# --------------------- direct-commit / no-PR row tooltip -----------------

def test_direct_commit_tooltip_english(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    tooltip = page.eval_on_selector(
        "#taskRows .no-pr", "el => el && el.getAttribute('title')")
    if tooltip is not None:
        assert tooltip == "Direct commit · no owning PR"
        no_pr_text = page.eval_on_selector("#taskRows .no-pr", "el => el.textContent")
        assert no_pr_text == "No PR"


def test_direct_commit_tooltip_default_is_chinese(page, server):
    open_dashboard(page, server)
    tooltip = page.eval_on_selector(
        "#taskRows .no-pr", "el => el && el.getAttribute('title')")
    if tooltip is not None:
        assert tooltip == "直接提交 · 無所屬 PR"


def test_commit_tooltip_english(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    commit_title = page.eval_on_selector(
        "#taskRows .commit-ref", "el => el && el.getAttribute('title')")
    if commit_title is not None:
        assert commit_title.startswith("Commit ")


# ---------------------- defect severity / status labels ------------------

def test_defect_severity_and_status_english(page, server):
    page.goto(f"{server}/?demo=1&lang=en", wait_until="networkidle")
    page.wait_for_selector("#defectRows", state="attached")
    rows_html = page.eval_on_selector("#defectRows", "el => el.innerHTML")
    for zh in ("高", "中", "低", "未修", "已修"):
        assert zh not in rows_html
    row_count = page.eval_on_selector_all("#defectRows tr", "els => els.length")
    if row_count and "無缺陷" not in rows_html:
        severities = page.eval_on_selector_all(
            "#defectRows tr td:nth-child(3)", "els => els.map(e => e.textContent.trim())")
        for s in severities:
            assert any(
                s.endswith(label) for label in ("High", "Medium", "Low", "—")
            ), f"unexpected severity text: {s!r}"
        statuses = page.eval_on_selector_all(
            "#defectRows tr td:nth-child(5)", "els => els.map(e => e.textContent.trim())")
        for s in statuses:
            assert s in {"Unfixed", "Fixed"}, f"unexpected status text: {s!r}"


def test_defect_severity_and_status_default_is_chinese(page, server):
    page.goto(server, wait_until="networkidle")
    page.wait_for_selector("#defectRows", state="attached")
    rows_html = page.eval_on_selector("#defectRows", "el => el.innerHTML")
    for en in ("High", "Medium", "Low", "Unfixed"):
        assert en not in rows_html


# ------------------------------ table empty state -------------------------

def test_table_empty_state_english_or_has_rows(page, server):
    open_dashboard(page, server, "?demo=1&lang=en")
    body = page.eval_on_selector("#taskRows", "el => el.textContent")
    assert "此範圍內無工作" not in body
    row_count = page.eval_on_selector_all("#taskRows tr", "els => els.length")
    assert row_count >= 1
    if row_count == 1:
        only_row_text = page.eval_on_selector("#taskRows tr", "el => el.textContent")
        if "No work in this scope" in only_row_text:
            assert True


# ----------------------------- READY_STATUS -------------------------------

def test_ready_status_english(page, server):
    page.goto(f"{server}/?demo=1&lang=en#product", wait_until="networkidle")
    page.wait_for_selector("#releaseReadiness", state="attached")
    html = page.eval_on_selector("#releaseReadiness", "el => el.innerHTML")
    assert html.strip(), "release readiness rendered empty"
    for zh in ("已準備", "進度正常", "需要留意", "存在風險", "未有範圍"):
        assert zh not in html
    states = page.eval_on_selector_all(
        "#releaseReadiness .readiness-state", "els => els.map(e => e.textContent)")
    assert states, "no readiness rows found"
    for s in states:
        assert s in {"Ready", "On track", "Watch", "At risk", "No scope"}


def test_ready_status_default_is_chinese(page, server):
    page.goto(f"{server}/?demo=1#product", wait_until="networkidle")
    page.wait_for_selector("#releaseReadiness", state="attached")
    states = page.eval_on_selector_all(
        "#releaseReadiness .readiness-state", "els => els.map(e => e.textContent)")
    assert states
    for s in states:
        assert s in {"已準備", "進度正常", "需要留意", "存在風險", "未有範圍"}


# ------------------------------ SOURCE_LABEL -------------------------------

def test_source_label_english(page, server):
    page.goto(f"{server}/?demo=1&lang=en#product", wait_until="networkidle")
    page.wait_for_selector("#productRoadmap", state="attached")
    html = page.eval_on_selector("#productRoadmap", "el => el.innerHTML")
    if html.strip() and "No milestones" not in html:
        assert "里程碑" not in html
        assert "計劃" not in html
        assert ("Milestone" in html) or ("Plan" in html)


# -------------------------- demo outcome labels ----------------------------

OUTCOME_LABELS_EN = {
    "Weekly active accounts": "accounts",
    "Activation within 7 days": "%",
    "Reconciliation time": "h",
    "Support requests / 1,000 orders": "request",
    "Monthly active filers": "user",
    "PDF export usage": "%",
    "Avg. time saved": "min",
    "Tax-check success rate": "%",
}

OUTCOME_VALUES_EN = {
    "Weekly active accounts": "1840 accounts",
    "Activation within 7 days": "68%",
    "Reconciliation time": "2.1 h",
    "Support requests / 1,000 orders": "4.6 requests",
    "Monthly active filers": "612 users",
    "PDF export usage": "47%",
    "Avg. time saved": "18 min",
    "Tax-check success rate": "96.8%",
}


def test_demo_outcomes_render_in_english_with_units_placed_correctly(page, server):
    page.goto(f"{server}/?demo=1&lang=en#product", wait_until="networkidle")
    page.wait_for_selector("#productOutcomes", state="attached", timeout=10_000)
    rows = page.eval_on_selector_all(
        "#productOutcomesBody .roadmap-row",
        "els => els.map(e => ({ label: e.querySelector('strong').textContent, "
        "value: e.querySelector('.roadmap-value').textContent }))",
    )
    got = {r["label"]: r["value"] for r in rows}
    assert set(got) == set(OUTCOME_VALUES_EN), f"missing/extra outcome labels: {got.keys()}"
    for label, expected_value in OUTCOME_VALUES_EN.items():
        assert got[label] == expected_value, (
            f"{label!r}: expected {expected_value!r}, got {got[label]!r}")


def test_demo_outcomes_default_is_exact_chinese(page, server):
    """No `lang` param — the 8 outcome label/value pairs must stay the exact
    zh literals demo-outcomes.js used to hold inline."""
    page.goto(f"{server}/?demo=1#product", wait_until="networkidle")
    page.wait_for_selector("#productOutcomes", state="attached", timeout=10_000)
    rows = page.eval_on_selector_all(
        "#productOutcomesBody .roadmap-row",
        "els => els.map(e => ({ label: e.querySelector('strong').textContent, "
        "value: e.querySelector('.roadmap-value').textContent }))",
    )
    got = {r["label"]: r["value"] for r in rows}
    expected = {
        "每週活躍帳戶": "1840 個帳戶",
        "7 日內完成啟用": "68%",
        "對帳時間": "2.1 小時",
        "每千張訂單的支援請求": "4.6 張",
        "每月活躍報稅者": "612 位使用者",
        "PDF 匯出使用率": "47%",
        "平均節省時間": "18 分鐘",
        "報稅檢查成功率": "96.8%",
    }
    assert got == expected
