"""Tests for the kpi + levels i18n extraction (Track B): docs/js/render-kpi.js
and docs/js/aggregate.js against docs/js/i18n/dict/{zh,en}/{kpi,levels}.js.

Mirrors the pattern in scripts/test_frontend_i18n.py (infrastructure) and
scripts/test_aggregate_js.py (module unit tests): no JS test runner in this
repo, so pure frontend logic is exercised by importing the ES module inside
a Playwright page and evaluating assertions there.

Run:  python -m pytest scripts/test_frontend_i18n_kpi.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="i18n tests need pytest-playwright")


def import_i18n(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="domcontentloaded")


def t(page, server, key: str, params=None, query: str = "?demo=1"):
    import_i18n(page, server, query)
    return page.evaluate(
        """
        async ({ key, params }) => {
          const m = await import('/js/i18n/index.js');
          return m.t(key, params);
        }
        """,
        {"key": key, "params": params},
    )


# ------------------------------ L1-L5 levels ------------------------------

def test_level_names_are_english_under_lang_en(page, server):
    query = "?demo=1&lang=en"
    assert t(page, server, "levels.L1", query=query) == "Assisted"
    assert t(page, server, "levels.L2", query=query) == "Partial"
    assert t(page, server, "levels.L3", query=query) == "Conditional"
    assert t(page, server, "levels.L4", query=query) == "High"
    assert t(page, server, "levels.L5", query=query) == "Full"
    assert t(page, server, "levels.untagged", query=query) == "Unclassified"


def test_level_names_are_chinese_by_default(page, server):
    """No `lang` param — the override contract: output must stay Chinese."""
    assert t(page, server, "levels.L1") == "輔助"
    assert t(page, server, "levels.L3") == "有條件自動"
    assert t(page, server, "levels.L5") == "完全自動"
    assert t(page, server, "levels.untagged") == "未分級"


def test_aggregate_meta_uses_translated_level_names_in_english(page, server):
    """aggregate.js META is built at module-eval time from t() — confirm the
    real module (not just the dict) reflects the translation."""
    page.goto(f"{server}/?demo=1&lang=en", wait_until="domcontentloaded")
    got = page.evaluate("""
        async () => {
          const m = await import('/js/aggregate.js');
          return {
            L1: m.META.L1.name,
            L4: m.META.L4.name,
          };
        }
    """)
    assert got == {"L1": "Assisted", "L4": "High"}


# ------------------------------ fmtHours ------------------------------

def evaluate_aggregate(page, server, body: str, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/aggregate.js'); "
        f"return ({body}); }}"
    )


def test_fmt_hours_hours_branch_english_keeps_span_markup(page, server):
    got = evaluate_aggregate(page, server, "m.fmtHours(5.25)", query="?demo=1&lang=en")
    assert got == '5.3 <span class="unit">h</span>'


def test_fmt_hours_days_branch_english_keeps_span_markup(page, server):
    """h >= 48 switches to the days branch (h / 24)."""
    got = evaluate_aggregate(page, server, "m.fmtHours(100)", query="?demo=1&lang=en")
    assert got == '4.2 <span class="unit">d</span>'


def test_fmt_hours_null_is_unchanged_in_both_languages(page, server):
    assert evaluate_aggregate(page, server, "m.fmtHours(null)", query="?demo=1") == "–"
    assert evaluate_aggregate(page, server, "m.fmtHours(null)", query="?demo=1&lang=en") == "–"


def test_fmt_hours_hours_branch_chinese_is_byte_identical_to_baseline(page, server):
    """Default (no lang) must stay exactly what the pre-i18n literal produced:
    h.toFixed(1) + '<span class="unit">小時</span>' with NO space."""
    got = evaluate_aggregate(page, server, "m.fmtHours(5.25)", query="?demo=1")
    assert got == '5.3<span class="unit">小時</span>'


def test_fmt_hours_days_branch_chinese_is_byte_identical_to_baseline(page, server):
    got = evaluate_aggregate(page, server, "m.fmtHours(100)", query="?demo=1")
    assert got == '4.2<span class="unit">日</span>'


# ------------------------------ DORA fallback ------------------------------

def test_dora_avg_every_n_weeks_fallback_interpolates_a_real_number(page, server):
    """The English word order differs from Chinese ('平均每 {weeks} 週 1 次' vs
    'avg. 1 every {weeks} weeks') — assert with a real, non-trivial weeks
    value threaded through interpolation, not hardcoded into the template."""
    got = t(page, server, "kpi.dora.deploySubLow",
            {"days": 90, "label": "deployments", "weeks": "3.7"},
            query="?demo=1&lang=en")
    assert got == "90 days (deployments) · avg. 1 every 3.7 weeks"


def test_dora_avg_every_n_weeks_fallback_chinese_matches_original_concatenation(page, server):
    got = t(page, server, "kpi.dora.deploySubLow",
            {"days": 90, "label": "部署", "weeks": "3.7"})
    assert got == "90 日內（部署）· 平均每 3.7 週 1 次"


# ------------------------------ alert messages ------------------------------

def test_alert_l3_down_title_english(page, server):
    got = t(page, server, "kpi.alerts.l3DownTitle", {"n": "12"}, query="?demo=1&lang=en")
    assert got == "L3+ share down 12 pp week-over-week"


def test_alert_low_coverage_title_english(page, server):
    got = t(page, server, "kpi.alerts.lowCoverageTitle", {"n": "62"}, query="?demo=1&lang=en")
    assert got == "Classification coverage low (62%)"


def test_alert_no_high_autonomy_title_and_detail_english(page, server):
    title = t(page, server, "kpi.alerts.noHighAutonomyTitle", query="?demo=1&lang=en")
    detail = t(page, server, "kpi.alerts.noHighAutonomyDetail", query="?demo=1&lang=en")
    assert title == "No L4+ work in the last two weeks"
    assert "automated verification" in detail


def test_alert_violation_title_pluralises_task_count(page, server):
    one = t(page, server, "kpi.alerts.violationTitle",
            {"n": 1, "prefix": "Red line", "label": "Oversized PR"}, query="?demo=1&lang=en")
    many = t(page, server, "kpi.alerts.violationTitle",
             {"n": 5, "prefix": "Red line", "label": "Oversized PR"}, query="?demo=1&lang=en")
    assert one == "Red line: 1 task Oversized PR"
    assert many == "Red line: 5 tasks Oversized PR"


def test_alert_none_is_exact_chinese_by_default(page, server):
    """Default (no lang param) — the empty-alerts fallback string is byte-
    identical to the original literal, including the ASCII (not fullwidth)
    comma."""
    got = t(page, server, "kpi.alerts.none")
    assert got == "暫無異常,指標喺正常範圍。"


# ------------------------------ RAG labels ------------------------------

def test_rag_labels_english(page, server):
    query = "?demo=1&lang=en"
    assert t(page, server, "kpi.rag.insufficient", query=query) == "Insufficient data"
    assert t(page, server, "kpi.rag.red", query=query) == "Red"
    assert t(page, server, "kpi.rag.amber", query=query) == "Amber"
    assert t(page, server, "kpi.rag.green", query=query) == "Green"


def test_rag_labels_chinese_by_default(page, server):
    assert t(page, server, "kpi.rag.insufficient") == "資料不足"
    assert t(page, server, "kpi.rag.red") == "紅"
    assert t(page, server, "kpi.rag.amber") == "黃"
    assert t(page, server, "kpi.rag.green") == "綠"


# ------------------------------ violation labels ------------------------------

VIOLATION_KEYS_EN = {
    "direct-push-main": "Direct push to a monitored branch (no PR)",
    "forbidden-files": "Committed .env / node_modules / __pycache__",
    "workflow-deleted": "Deleted a GitHub Actions workflow",
    "cross-branch-merge": "Cross-feature-branch merge",
    "core-without-double-review": "Core module change without double review",
    "merged-without-review": "Merged without any review",
    "oversized-pr": "Oversized PR (not staged into smaller commits)",
}


def test_all_seven_violation_labels_english(page, server):
    for key, expected in VIOLATION_KEYS_EN.items():
        got = t(page, server, f"kpi.violations.{key}", query="?demo=1&lang=en")
        assert got == expected, f"{key}: got {got!r}"


def test_aggregate_violation_meta_reflects_translated_labels(page, server):
    page.goto(f"{server}/?demo=1&lang=en", wait_until="domcontentloaded")
    got = page.evaluate("""
        async () => {
          const m = await import('/js/aggregate.js');
          return Object.fromEntries(
            Object.entries(m.VIOLATION_META).map(([k, v]) => [k, v.label])
          );
        }
    """)
    assert got == VIOLATION_KEYS_EN


def test_violation_labels_chinese_are_byte_identical_to_baseline(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    got = page.evaluate("""
        async () => {
          const m = await import('/js/aggregate.js');
          return m.VIOLATION_META['forbidden-files'].label;
        }
    """)
    assert got == "提交咗 .env / node_modules / __pycache__"


# ------------------------------ explicit LOCALE fix ------------------------------

def test_kpi_task_counts_use_explicit_locale_not_browser_default(page, server):
    """render-kpi.js:31 used to call toLocaleString() with no locale argument
    — a latent bug. Spy on Number.prototype.toLocaleString and assert every
    call during renderKPIs() received the explicit LOCALE export."""
    page.goto(f"{server}/?demo=1&lang=en", wait_until="domcontentloaded")
    calls = page.evaluate("""
        async () => {
          const calls = [];
          const orig = Number.prototype.toLocaleString;
          Number.prototype.toLocaleString = function (...args) {
            calls.push(args[0]);
            return orig.apply(this, args);
          };
          const kpi = await import('/js/render-kpi.js');
          const cur = { l3plus: 3, tagged: 1234, insAi: 5, insTotal: 20, total: 5678, untagged: 2, byLevel: {} };
          const prev = { l3plus: 2, tagged: 8, insAi: 4, insTotal: 18, total: 10, untagged: 1, byLevel: {} };
          kpi.renderKPIs(cur, prev);
          Number.prototype.toLocaleString = orig;
          return calls;
        }
    """)
    assert calls, "toLocaleString() was never called by renderKPIs()"
    assert all(c == "en" for c in calls), f"expected explicit 'en' on every call, got {calls}"


def test_kpi_task_counts_use_explicit_zh_hant_locale_by_default(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    calls = page.evaluate("""
        async () => {
          const calls = [];
          const orig = Number.prototype.toLocaleString;
          Number.prototype.toLocaleString = function (...args) {
            calls.push(args[0]);
            return orig.apply(this, args);
          };
          const kpi = await import('/js/render-kpi.js');
          const cur = { l3plus: 3, tagged: 1234, insAi: 5, insTotal: 20, total: 5678, untagged: 2, byLevel: {} };
          const prev = { l3plus: 2, tagged: 8, insAi: 4, insTotal: 18, total: 10, untagged: 1, byLevel: {} };
          kpi.renderKPIs(cur, prev);
          Number.prototype.toLocaleString = orig;
          return calls;
        }
    """)
    assert calls, "toLocaleString() was never called by renderKPIs()"
    assert all(c == "zh-Hant" for c in calls), f"expected explicit 'zh-Hant' on every call, got {calls}"


# ------------------------------ plural counters (real i18n, not `+ 's'`) ------------------------------

def test_untagged_sub_pluralises_task_count_in_english(page, server):
    query = "?demo=1&lang=en"
    one = t(page, server, "kpi.untaggedSub", {"n": 1, "count": "1"}, query=query)
    many = t(page, server, "kpi.untaggedSub", {"n": 7, "count": "7"}, query=query)
    assert one == "1 unclassified task"
    assert many == "7 unclassified tasks"


def test_untagged_sub_chinese_has_no_plural_distinction(page, server):
    one = t(page, server, "kpi.untaggedSub", {"n": 1, "count": "1"})
    many = t(page, server, "kpi.untaggedSub", {"n": 7, "count": "7"})
    assert one == "未分級 1 項工作"
    assert many == "未分級 7 項工作"
