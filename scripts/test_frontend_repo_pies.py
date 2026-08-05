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
        "open_tasks": [
            {"title": "plan bug", "bug": True, "assignee": None},
        ],
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
    alpha["issues"] = {
        "open": [
            {"title": "issue bug", "labels": ["bug"], "assignees": ["wing-csi"]},
            {"title": "not a bug", "labels": ["feature"], "assignees": ["wing-csi"]},
        ],
        "closed_recent": [
            {"title": "fixed issue", "labels": ["bug"], "assignees": ["Tony"]},
        ],
    }
    return data


def _open(page, server, data=None):
    page.route("**/data/metrics.json", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(data or _data(), ensure_ascii=False)))
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


def test_plan_pie_uses_repo_owner_for_tasks_without_an_explicit_assignee(page, server):
    dash = _open(page, server)
    legend = _legend(dash, "#planAssignmentPie")
    assert "7 / 10 · 70.0%" in legend["Wing"]
    assert "3 / 10 · 30.0%" in legend["Tony"]
    assert "未指定" not in legend
    assert dash.text_content("#planAssignmentPie .pie-total").strip() == "10"
    assert dash.text_content("#planAssignmentPie .pie-total-label").strip() == "項工作"


def test_legacy_plan_payload_uses_repo_owner_instead_of_looking_unassigned(page, server):
    data = _data()
    del data["repo_meta"]["acme/alpha"]["plan"]["assignments"]
    del data["repo_meta"]["acme/alpha"]["plan"]["unassigned"]
    dash = _open(page, server, data)
    legend = _legend(dash, "#planAssignmentPie")
    assert "10 / 10 · 100.0%" in legend["Wing"]


def test_plan_tasks_stay_unassigned_when_the_repo_has_no_owner(page, server):
    data = _data()
    del data["repo_meta"]["acme/alpha"]["owner"]
    dash = _open(page, server, data)
    legend = _legend(dash, "#planAssignmentPie")
    assert "4 / 10 · 40.0%" in legend["Wing"]
    assert "3 / 10 · 30.0%" in legend["Tony"]
    assert "3 / 10 · 30.0%" in legend["未指定"]


def test_defect_pie_reports_total_open_and_each_fixer(page, server):
    dash = _open(page, server)
    legend = _legend(dash, "#defectFixPie")
    assert "1 / 8 · 12.5%" in legend["Wing"]
    assert "2 / 8 · 25.0%" in legend["Tony"]
    assert "1 / 8 · 12.5%" in legend["已修 · 未指定"]
    assert "4 / 8 · 50.0%" in legend["未修"]
    assert dash.text_content("#defectFixPie .pie-total").strip() == "8"
    assert dash.text_content("#defectFixPie .pie-total-label").strip() == "4 已修"


def test_person_filter_highlights_but_does_not_narrow_repo_pies(page, server):
    dash = _open(page, server)
    before = dash.inner_html("#planAssignmentPie")
    dash.select_option("#personSel", "Wing")
    after = dash.inner_html("#planAssignmentPie")
    assert "7 / 10 · 70.0%" in dash.text_content("#planAssignmentPie")
    assert dash.locator(
        '#planAssignmentPie .pie-legend-row[data-name="Wing"].is-selected'
    ).count() == 1
    assert before != after
    assert dash.locator("#planAssignmentPie .pie-legend-row").count() == 2
    assert dash.locator(".register-pie .scope-note:visible").count() == 2


def test_repo_without_register_data_has_explicit_empty_states(page, server):
    dash = _open(page, server)
    dash.select_option("#repoSel", "acme/beta")
    assert "未有可用分配數據" in dash.text_content("#planAssignmentPie")
    assert "未有缺陷數據" in dash.text_content("#defectFixPie")


def test_repo_pies_do_not_overflow_phone_width(page, server):
    page.set_viewport_size({"width": 375, "height": 812})
    dash = _open(page, server)
    assert dash.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_pie_viewbox_does_not_magnify_the_type_scale(page, server):
    dash = _open(page, server)
    sizes = dash.eval_on_selector(
        "#planAssignmentPie .pie-svg",
        """svg => ({
          cssWidth: svg.getBoundingClientRect().width,
          viewBoxWidth: svg.viewBox.baseVal.width,
          screenScale: svg.getScreenCTM().a,
          totalSize: parseFloat(getComputedStyle(svg.querySelector('.pie-total')).fontSize),
          labelSize: parseFloat(getComputedStyle(svg.querySelector('.pie-total-label')).fontSize),
          titleSize: parseFloat(getComputedStyle(document.querySelector('#planAssignmentTitle')).fontSize),
        })""",
    )
    assert sizes["viewBoxWidth"] == sizes["cssWidth"] == 190
    assert sizes["screenScale"] == pytest.approx(1, abs=0.05)
    assert sizes["totalSize"] == 26
    assert sizes["labelSize"] == 14
    assert sizes["titleSize"] == 22

    defect_sizes = dash.eval_on_selector(
        "#defectFixPie .pie-svg",
        """svg => ({
          totalSize: parseFloat(getComputedStyle(svg.querySelector('.pie-total')).fontSize),
          titleSize: parseFloat(getComputedStyle(document.querySelector('#defectFixTitle')).fontSize),
        })""",
    )
    assert defect_sizes["totalSize"] == 26
    assert defect_sizes["titleSize"] == 22


def test_pie_explanations_use_plain_readable_language(page, server):
    dash = _open(page, server)
    assert dash.text_content("#planAssignmentTitle").strip() == "Plan 工作分配"
    assert dash.text_content("#planAssignmentTitle + p").strip() == \
        "assignee:Name / @GitHub-handle task 數 ÷ plan 總 task 數 · 未標記則使用程式庫負責人"
    assert dash.text_content("#defectFixTitle").strip() == "Defect 修復分佈"
    assert dash.text_content("#defectFixTitle + p").strip() == \
        "fixed-by:Name · 未修亦計入總數"
