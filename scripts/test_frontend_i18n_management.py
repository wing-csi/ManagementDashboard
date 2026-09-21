"""i18n string-extraction tests for TRACK D: management summary and projects.

Covers docs/js/render-management.js, docs/js/management.js and
docs/js/render-project.js against docs/js/i18n/dict/{zh,en}/management.js
and docs/js/i18n/dict/{zh,en}/project.js.

Two layers:
  * Direct t() lookups against the real dictionaries — fast, deterministic,
    covers every STATUS/HEALTH/CONFIDENCE/FORECAST_REASON label, the
    project priority/risk labels, and the interpolated tooltip templates.
  * Real function calls (deriveManagement, issueScore) with explicit
    `todayStr` — proves the *wiring*, not just the dictionary content.

With no ?lang= param, LANG resolves to 'zh' and every assertion below that
checks the no-lang-param path must match the exact pre-i18n Chinese
literal — this is the override-layer contract test_frontend_snapshot.py
also pins for docs/js/render-project.js output.

Run:  python -m pytest scripts/test_frontend_i18n_management.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="i18n tests need pytest-playwright")


def t(page, server, key: str, params: dict | None = None, lang: str | None = None):
    """Call the real t() against the real dictionary for one key."""
    query = f"?demo=1&lang={lang}" if lang else "?demo=1"
    page.goto(f"{server}/{query}", wait_until="domcontentloaded")
    return page.evaluate(
        """async ([key, params]) => {
            const m = await import('/js/i18n/index.js');
            return m.t(key, params || undefined);
        }""",
        [key, params],
    )


def evaluate_management(page, server, body: str, lang: str | None = None):
    query = f"?demo=1&lang={lang}" if lang else "?demo=1"
    page.goto(f"{server}/{query}", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/management.js'); "
        f"return ({body}); }}"
    )


def evaluate_project(page, server, body: str, lang: str | None = None):
    query = f"?demo=1&lang={lang}" if lang else "?demo=1"
    page.goto(f"{server}/{query}", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/render-project.js'); "
        f"return ({body}); }}"
    )


# ------------------------------ STATUS (4) ------------------------------

@pytest.mark.parametrize("key,zh,en", [
    ("management.status.onTrack", "進度正常", "On track"),
    ("management.status.atRisk", "存在風險", "At risk"),
    ("management.status.offTrack", "偏離計劃", "Off track"),
    ("management.status.unknown", "未知", "Unknown"),
])
def test_status_labels(page, server, key, zh, en):
    assert t(page, server, key) == zh
    assert t(page, server, key, lang="en") == en


# ------------------------------ HEALTH (6) -------------------------------

@pytest.mark.parametrize("key,zh,en", [
    ("management.health.healthy", "最新", "Current"),
    ("management.health.attention", "需要關注", "Needs attention"),
    ("management.health.stale", "已過時", "Stale"),
    ("management.health.unreadable", "未知", "Unknown"),
    ("management.health.future", "時鐘不一致", "Clock mismatch"),
    ("management.health.unknown", "未知", "Unknown"),
])
def test_health_labels(page, server, key, zh, en):
    assert t(page, server, key) == zh
    assert t(page, server, key, lang="en") == en


def test_health_stale_is_exactly_stale_for_the_demo_trust_moment(page, server):
    """The client runbook has the presenter quote this string verbatim."""
    assert t(page, server, "management.health.stale", lang="en") == "Stale"


def test_health_unknown_is_exactly_unknown_for_the_demo_trust_moment(page, server):
    assert t(page, server, "management.health.unknown", lang="en") == "Unknown"


# --------------------------- CONFIDENCE (4) ------------------------------

@pytest.mark.parametrize("key,zh,en", [
    ("management.confidence.actual", "實際", "Actual"),
    ("management.confidence.high", "高", "High"),
    ("management.confidence.medium", "中", "Medium"),
    ("management.confidence.low", "低", "Low"),
])
def test_confidence_labels(page, server, key, zh, en):
    assert t(page, server, key) == zh
    assert t(page, server, key, lang="en") == en


# ------------------------- FORECAST_REASON (4) ---------------------------

@pytest.mark.parametrize("key,zh,en", [
    ("management.forecastReason.noPlan", "未有計劃", "No plan"),
    ("management.forecastReason.notEnoughHistory", "觀測點不足", "Too few observations"),
    ("management.forecastReason.historyTooShort", "歷史少過 7 日", "Under 7 days of history"),
    ("management.forecastReason.noObservedProgress", "未觀測到完成進度", "No observed progress"),
])
def test_forecast_reason_labels(page, server, key, zh, en):
    assert t(page, server, key) == zh
    assert t(page, server, key, lang="en") == en


# ------------------------- headline plural counts -------------------------

def test_headline_off_track_count_plural(page, server):
    zh_one = t(page, server, "management.headline.countOffTrack", {"n": 1})
    zh_other = t(page, server, "management.headline.countOffTrack", {"n": 3})
    assert zh_one == "1 個偏離計劃"
    assert zh_other == "3 個偏離計劃"
    en_one = t(page, server, "management.headline.countOffTrack", {"n": 1}, lang="en")
    en_other = t(page, server, "management.headline.countOffTrack", {"n": 3}, lang="en")
    assert en_one == "1 project off track"
    assert en_other == "3 projects off track"


# ------------------------- project priority / risk -------------------------

@pytest.mark.parametrize("key,zh,en", [
    ("project.priority.p0", "P0 / 嚴重", "P0 / Critical"),
    ("project.priority.high", "高優先", "High priority"),
    ("project.priority.medium", "中優先", "Medium priority"),
    ("project.risk.high", "高風險", "High risk"),
    ("project.risk.medium", "中風險", "Medium risk"),
    ("project.risk.normal", "正常", "Normal"),
])
def test_project_priority_and_risk_labels(page, server, key, zh, en):
    assert t(page, server, key) == zh
    assert t(page, server, key, lang="en") == en


# ------------------------------ tooltips -----------------------------------

def test_project_chip_plan_tooltip_source_label(page, server):
    params = {"path": "plan.md", "done": 3, "total": 12}
    assert t(page, server, "project.chip.tooltipSourceLabel", params) == \
        "範圍來源：plan.md（3/12 個核取方塊）"
    assert t(page, server, "project.chip.tooltipSourceLabel", params, lang="en") == \
        "Scope source: plan.md (3/12 checkboxes)"


def test_project_chip_issue_tooltip(page, server):
    params = {"done": 7, "open": 5, "overdue": 2, "stale": 1}
    zh = t(page, server, "project.chip.issueTooltip", params)
    en = t(page, server, "project.chip.issueTooltip", params, lang="en")
    assert zh == "完成 7 / 剩餘 5 · 延誤 2 · 呆滯 1 · 分母 = 已建立的 GitHub Issue，未拆成 Issue 的範圍無法顯示"
    assert en == "Completed 7 / Remaining 5 · Overdue 2 · Stalled 1 · Denominator = created GitHub Issues; scope not yet split into Issues cannot be shown"


def test_project_milestone_section_tooltip(page, server):
    params = {"title": "Phase 2", "path": "plan.md"}
    assert t(page, server, "project.milestone.sectionTooltip", params) == "Phase 2（plan.md）"
    assert t(page, server, "project.milestone.sectionTooltip", params, lang="en") == "Phase 2 (plan.md)"


# ---------------------------- default is Chinese ----------------------------

def test_default_no_lang_param_is_exact_chinese(page, server):
    """No ?lang= at all (not even ?demo=1&lang=zh) must resolve to zh."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    got = page.evaluate("""
        async () => {
          const m = await import('/js/i18n/index.js');
          return {
            status: m.t('management.status.offTrack'),
            health: m.t('management.health.stale'),
            priority: m.t('project.priority.p0'),
          };
        }
    """)
    assert got == {"status": "偏離計劃", "health": "已過時", "priority": "P0 / 嚴重"}


# ------------------------- deriveManagement wiring -------------------------

DATA_HIGH_OVERDUE = """{
  generated_at:'2026-08-05T12:00:00Z', repos:['acme/app'], tasks:[], errors:[],
  repo_meta:{'acme/app':{plan:{path:'plan.md',done:1,total:3,due_max:'2026-08-20',
    open_tasks:[{title:'Ship blocker',due:'2026-08-01',priority:'P1'}],
    history:[{date:'2026-07-01',done:0,total:3},{date:'2026-08-05',done:1,total:3}]}}}
}"""


def test_attention_high_overdue_singular(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_HIGH_OVERDUE}, "
        "{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')})",
    )
    assert any("1 個高優先項目逾期" in r for r in got["projects"][0]["reasons"])


def test_attention_high_overdue_singular_en(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_HIGH_OVERDUE}, "
        "{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')})",
        lang="en",
    )
    assert any("1 high-priority item overdue" in r for r in got["projects"][0]["reasons"])


DATA_TWO_OVERDUE = """{
  generated_at:'2026-08-05T12:00:00Z', repos:['acme/app'], tasks:[], errors:[],
  repo_meta:{'acme/app':{plan:{path:'plan.md',done:1,total:5,due_max:'2026-09-20',
    open_tasks:[
      {title:'A',due:'2026-08-01',priority:'P1'},
      {title:'B',due:'2026-08-02',priority:'P0'}
    ],
    history:[{date:'2026-07-01',done:0,total:5},{date:'2026-08-05',done:1,total:5}]}}}
}"""


def test_attention_high_overdue_plural_en(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_TWO_OVERDUE}, "
        "{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')})",
        lang="en",
    )
    assert any("2 high-priority items overdue" in r for r in got["projects"][0]["reasons"])


def test_attention_high_overdue_plural_zh(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_TWO_OVERDUE}, "
        "{todayStr:'2026-08-05', nowMs:Date.parse('2026-08-05T13:00:00Z')})",
    )
    assert any("2 個高優先項目逾期" in r for r in got["projects"][0]["reasons"])


DATA_STALE_SNAPSHOT_ITEM = """{
  generated_at:'2026-07-01T12:00:00Z', repos:['acme/app'], tasks:[], errors:[],
  repo_meta:{'acme/app':{issues_error:'Resource not accessible by token'}}
}"""


def test_attention_items_stale_data_and_issue_collection_zh(page, server):
    """At least 3 distinct attention items land: stale-data, issue-collection
    failure, and (via the missing-plan reason) an 'unknown' project."""
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_STALE_SNAPSHOT_ITEM}, "
        "{todayStr:'2026-09-20', nowMs:Date.parse('2026-09-20T13:00:00Z')})",
    )
    titles = [item["title"] for item in got["attention"]]
    assert "儀表板數據唔新鮮" in titles
    assert any("收集唔到 GitHub Issue" in title for title in titles)
    assert len(got["attention"]) >= 2
    assert got["projects"][0]["status"] == "unknown"
    assert any("未有計劃範圍" in r for r in got["projects"][0]["reasons"])


def test_attention_items_stale_data_and_issue_collection_en(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_STALE_SNAPSHOT_ITEM}, "
        "{todayStr:'2026-09-20', nowMs:Date.parse('2026-09-20T13:00:00Z')})",
        lang="en",
    )
    titles = [item["title"] for item in got["attention"]]
    assert "Dashboard data not fresh" in titles
    assert any("repository could not collect GitHub Issues" in title for title in titles)
    assert any("No planned scope" in r for r in got["projects"][0]["reasons"])


DATA_STALE_ISSUES_AND_REDLINE = """{
  generated_at:'2026-09-20T12:00:00Z', repos:['acme/app'], errors:[],
  tasks:[{repo:'acme/app', title:'Bad merge', violations:['direct-push-main']}],
  repo_meta:{'acme/app':{plan:{path:'plan.md',done:3,total:4,due_max:'2026-12-01',
    open_tasks:[],
    history:[{date:'2026-08-01',done:0,total:4},{date:'2026-09-20',done:3,total:4}]},
    issues:{open:[
      {title:'Stale one', due:null, updated:'2026-08-01', labels:[]}
    ], open_total:1, closed_total:0, milestones:[]}}}
}"""


def test_reasons_stale_issues_and_redline_zh(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_STALE_ISSUES_AND_REDLINE}, "
        "{todayStr:'2026-09-20', nowMs:Date.parse('2026-09-20T13:00:00Z')})",
    )
    reasons = got["projects"][0]["reasons"]
    assert any("1 個 GitHub Issue 呆滯" in r for r in reasons)
    assert any(item["kind"] == "redline" and item["title"] == "Bad merge"
               for item in got["attention"])
    assert any("治理紅線" in item["detail"] for item in got["attention"] if item["kind"] == "redline")


def test_reasons_stale_issues_and_redline_en(page, server):
    got = evaluate_management(
        page, server,
        f"m.deriveManagement({DATA_STALE_ISSUES_AND_REDLINE}, "
        "{todayStr:'2026-09-20', nowMs:Date.parse('2026-09-20T13:00:00Z')})",
        lang="en",
    )
    reasons = got["projects"][0]["reasons"]
    assert any("1 GitHub Issue stalled" in r for r in reasons)
    assert any("Governance redline" in item["detail"] for item in got["attention"]
               if item["kind"] == "redline")


# ------------------------------ issueScore ----------------------------------

def test_issue_score_priority_and_overdue_labels_zh(page, server):
    iss = "{due:'2026-08-01', labels:['P1'], created:'2026-07-01'}"
    got = evaluate_project(page, server, f"m.issueScore({iss}, '2026-08-10')")
    why = got["why"]
    assert any("遲咗 9 日" in w for w in why)
    assert "高優先" in why
    assert any("開咗" in w for w in why)


def test_issue_score_priority_and_overdue_labels_en(page, server):
    iss = "{due:'2026-08-01', labels:['P1'], created:'2026-07-01'}"
    got = evaluate_project(page, server, f"m.issueScore({iss}, '2026-08-10')", lang="en")
    why = got["why"]
    assert any("9 days overdue" in w for w in why)
    assert "High priority" in why
    assert any("open" in w for w in why)


def test_issue_score_overdue_singular_day_en(page, server):
    iss = "{due:'2026-08-09', labels:[], created:null}"
    got = evaluate_project(page, server, f"m.issueScore({iss}, '2026-08-10')", lang="en")
    assert any("1 day overdue" in w for w in got["why"])


def test_issue_score_bug_label(page, server):
    iss = "{due:null, labels:['bug'], created:null}"
    zh = evaluate_project(page, server, f"m.issueScore({iss}, '2026-08-10')")
    en = evaluate_project(page, server, f"m.issueScore({iss}, '2026-08-10')", lang="en")
    assert "缺陷" in zh["why"]
    assert "Defect" in en["why"]
