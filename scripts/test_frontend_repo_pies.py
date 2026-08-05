"""Repo 概覽 pies: plan assignment contribution and defect repair ownership."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright", reason="repo pie tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-defects.json"


def _data() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    alpha = data["repo_meta"]["acme/alpha"]
    alpha["plan"] = {
        "done": 4,
        "total": 10,
        "path": "docs/plan.md",
        "sections": [],
        "open_tasks": [],
        "assignments": [
            {"name": "wing-csi", "tasks": 4},
            {"name": "Tony", "tasks": 3},
        ],
        "unassigned": 3,
    }
    alpha["defects"]["items"] = [
        {"title": "open one", "open": True, "fixed_by": None},
        {"title": "open two", "open": True, "fixed_by": None},
        {"title": "fixed one", "open": False, "fixed_by": "wing-csi"},
        {"title": "fixed two", "open": False, "fixed_by": "Tony"},
        {"title": "fixed three", "open": False, "fixed_by": None},
    ]
    return data


def _open(page, server):
    page.route("**/data/metrics.json", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(_data(), ensure_ascii=False)))
    page.goto(server, wait_until="networkidle")
    page.click("#tab-projects")
    page.wait_for_selector("#planAssignmentPie .pie-svg", state="visible")
    return page


def _legend(page, selector: str) -> dict[str, str]:
    rows = page.eval_on_selector_all(
        f"{selector} .pie-legend-row",
        "els => els.map(e => [e.dataset.name, e.innerText.trim()])",
    )
    return dict(rows)


def test_plan_pie_is_assigned_task_count_over_total(page, server):
    dash = _open(page, server)
    legend = _legend(dash, "#planAssignmentPie")
    assert "4 / 10 · 40.0%" in legend["Wing"]
    assert "3 / 10 · 30.0%" in legend["Tony"]
    assert "3 / 10 · 30.0%" in legend["未指定"]
    assert dash.text_content("#planAssignmentPie .pie-total").strip() == "10"


def test_defect_pie_reports_total_open_and_each_fixer(page, server):
    dash = _open(page, server)
    legend = _legend(dash, "#defectFixPie")
    assert "1 / 5 · 20.0%" in legend["Wing"]
    assert "1 / 5 · 20.0%" in legend["Tony"]
    assert "1 / 5 · 20.0%" in legend["已修 · 未指定"]
    assert "2 / 5 · 40.0%" in legend["未修"]
    assert dash.text_content("#defectFixPie .pie-total").strip() == "5"
    assert dash.text_content("#defectFixPie .pie-total-label").strip() == "3 fixed"


def test_person_filter_highlights_but_does_not_narrow_repo_pies(page, server):
    dash = _open(page, server)
    before = dash.inner_html("#planAssignmentPie")
    dash.select_option("#personSel", "Wing")
    after = dash.inner_html("#planAssignmentPie")
    assert "4 / 10 · 40.0%" in dash.text_content("#planAssignmentPie")
    assert dash.locator(
        '#planAssignmentPie .pie-legend-row[data-name="Wing"].is-selected'
    ).count() == 1
    assert before != after
    assert dash.locator("#planAssignmentPie .pie-legend-row").count() == 3
    assert dash.locator(".register-pie .scope-note:visible").count() == 2


def test_repo_without_register_data_has_explicit_empty_states(page, server):
    dash = _open(page, server)
    dash.select_option("#repoSel", "acme/beta")
    assert "未有可用分配數據" in dash.text_content("#planAssignmentPie")
    assert "未有 defect 登記冊數據" in dash.text_content("#defectFixPie")


def test_repo_pies_do_not_overflow_phone_width(page, server):
    page.set_viewport_size({"width": 375, "height": 812})
    dash = _open(page, server)
    assert dash.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
