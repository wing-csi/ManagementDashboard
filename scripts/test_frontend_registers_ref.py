"""登記冊住喺另一條 branch 時,前端條 link 要指返嗰條 branch。

plan.md / defect.md 唔一定要 merge 入 default branch — 一條 `docs/*` branch
放住兩份登記冊,collector 用 config 嘅 `registers_ref` 讀返(見
`_contents_path()`),然後喺 meta 度記低條 branch。

前端本來一律砌 `blob/HEAD/<path>`,而 HEAD = default branch。登記冊唔喺
default branch 嘅話,卡同表照樣有數,但每一行撳落去都係 404 — 一個「有數據
但跟唔到」嘅狀態,比乾脆冇 link 更難察覺。

三個砌 link 嘅位都要跟:缺陷登記冊行、plan file 帶 `#bug` 嘅行(兩個都喺
Defect 追蹤表),同埋項目側嘅今日建議。

Run:  python -m pytest scripts/test_frontend_registers_ref.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="registers_ref link tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-defects.json"
REF = "docs/management-dashboard-registers"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _with_plan(data: dict, ref: str | None) -> dict:
    """acme/alpha 加一份 plan file(fixture 冇),帶一個 `#bug` 未完成項目。"""
    data["repo_meta"]["acme/alpha"]["plan"] = {
        "done": 1, "total": 2, "path": "plan.md", "ref": ref,
        "sections": [{"title": "Phase 2", "done": 1, "total": 2}],
        "open_tasks": [{"title": "fix: rounding 錯數", "due": None,
                        "priority": "P0", "bug": True, "section": "Phase 2"}],
    }
    return data


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


def _defect_row(page, title: str) -> dict:
    rows = page.eval_on_selector_all(
        "#defectRows tr",
        "els => els.map(e => ({text: e.innerText,"
        " href: (e.querySelector('a.tlink') || {}).href || ''}))")
    return next(r for r in rows if title in r["text"])


# ------------------------- 缺陷登記冊嗰半 -------------------------

def test_a_branch_hosted_defect_register_links_to_that_branch(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["defects"]["ref"] = REF
    _serve(page, data)
    dash = _open(page, server)
    row = _defect_row(dash, "匯出 CSV 中文亂碼")
    assert row["href"].endswith(f"/acme/alpha/blob/{REF}/docs/defects.md")


def test_a_register_on_the_default_branch_still_links_to_head(page, server):
    """絕大部分 repo 唔會設 registers_ref — 佢哋條 link 要一個字都冇變。"""
    _serve(page, _load())
    dash = _open(page, server)
    row = _defect_row(dash, "匯出 CSV 中文亂碼")
    assert row["href"].endswith("/acme/alpha/blob/HEAD/docs/defects.md")


# --------------------------- plan file 嗰半 ---------------------------

def test_a_branch_hosted_plan_file_bug_links_to_that_branch(page, server):
    """plan_file 同 defect_file 共用同一個 registers_ref,所以 plan 嗰半
    一樣要跟 — 淨係修好一半,另一半照樣派 404。"""
    _serve(page, _with_plan(_load(), REF))
    dash = _open(page, server)
    row = _defect_row(dash, "fix: rounding 錯數")
    assert row["href"].endswith(f"/acme/alpha/blob/{REF}/plan.md")


def test_a_plan_file_on_the_default_branch_still_links_to_head(page, server):
    _serve(page, _with_plan(_load(), None))
    dash = _open(page, server)
    row = _defect_row(dash, "fix: rounding 錯數")
    assert row["href"].endswith("/acme/alpha/blob/HEAD/plan.md")


# ----------------------- 項目側嘅今日建議 -----------------------

def test_the_project_suggestions_link_to_the_branch_too(page, server):
    """今日建議自己砌一次 link — 唔係經 Defect 追蹤表嗰條路,
    所以要獨立守住。"""
    _serve(page, _with_plan(_load(), REF))
    dash = _open(page, server)
    dash.wait_for_selector("#projTodo a.tlink", state="attached")
    hrefs = dash.eval_on_selector_all("#projTodo a.tlink", "els => els.map(e => e.href)")
    assert any(h.endswith(f"/acme/alpha/blob/{REF}/plan.md") for h in hrefs)
