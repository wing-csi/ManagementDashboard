"""Behaviour tests for the 缺陷率 card fed by the per-repo defect register.

The register is a hand-maintained `defect.md` in each tracked repo, configured
with `defect_file`. It exists because GitHub Issues carry no signal here: 1 of
14 repos has issue data and it reports zero issues, so the Defect 追蹤 table
had nothing to show.

Two numbers come off one card: 缺陷率 (defects found inside the window ÷ tasks
delivered in the same window) as the value, and the open backlog in the
sub-line.

The denominator is deliberately repo-wide even under a person filter. defect.md
has no author dimension, so dividing repo-wide defects by one person's tasks
would repeat exactly the mistake 變更失敗率 made — a numerator and denominator
on different scopes is not a rate. The card carries the 全 repo 範圍 note the
other repo-level surfaces use.

Fixture arithmetic (acme/alpha has a register, acme/beta has none):
  10 tasks in window · 5 defects · 3 found in window · 4 open · 1 undated
  → 3/10 = 30.0%

Run:  python -m pytest scripts/test_frontend_defects.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="缺陷率 tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-defects.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


@pytest.fixture()
def defect_page(page):
    _serve(page, _load_fixture())
    return page


def open_dashboard(defect_page, server, query: str = ""):
    defect_page.goto(f"{server}/{query}", wait_until="networkidle")
    defect_page.wait_for_selector("#taskRows tr", state="attached")
    return defect_page


# ------------------------------ the rate ------------------------------

def test_rate_is_defects_found_in_window_over_tasks_in_window(defect_page, server):
    page = open_dashboard(defect_page, server)
    assert page.text_content("#qDefect").strip() == "30.0%"


def test_subtext_reports_both_sides_the_backlog_and_the_undated(defect_page, server):
    page = open_dashboard(defect_page, server)
    sub = page.text_content("#qDefectSub")
    assert "3" in sub and "10" in sub      # 3 found / 10 tasks
    assert "4 個未修" in sub                # the backlog, a snapshot
    assert "found:" in sub                 # the undated defect is declared


def test_a_defect_found_outside_the_window_stays_in_the_backlog(defect_page, server):
    """It cannot enter a windowed rate, but a bug open since 2019 is exactly
    what a backlog number exists to show."""
    page = open_dashboard(defect_page, server)
    assert "4 個未修" in page.text_content("#qDefectSub")
    assert page.text_content("#qDefect").strip() == "30.0%"   # 3, not 4


def test_an_undated_defect_is_excluded_from_the_rate_but_declared(defect_page, server):
    """Silently dropping it would depress the rate where nobody can see it."""
    items = _load_fixture()["repo_meta"]["acme/alpha"]["defects"]["items"]
    assert sum(1 for i in items if i["found"] is None) == 1
    page = open_dashboard(defect_page, server)
    assert "found:" in page.text_content("#qDefectSub")


# --------------------------- scope behaviour ---------------------------

def test_denominator_stays_repo_wide_under_a_person_filter(defect_page, server):
    """The 變更失敗率 lesson. Wing owns 6 of the 10 tasks; if the filter
    narrowed the denominator the card would read 50%, dividing repo-wide
    defects by one person's output."""
    page = open_dashboard(defect_page, server)
    page.select_option("#personSel", "Wing")
    assert page.text_content("#qDefect").strip() == "30.0%"


def test_the_card_is_marked_repo_wide_when_a_person_is_selected(defect_page, server):
    page = open_dashboard(defect_page, server)
    visible = "els => els.filter(e => !e.hidden).length"
    before = page.eval_on_selector_all("#qDefectScope", visible)
    page.select_option("#personSel", "Wing")
    after = page.eval_on_selector_all("#qDefectScope", visible)
    assert before == 0 and after == 1


def test_a_repo_filter_does_narrow_both_sides(defect_page, server):
    """Unlike the person filter, a repo filter is a dimension the register
    has: acme/alpha holds all 3 in-window defects and 6 of the 10 tasks."""
    page = open_dashboard(defect_page, server)
    page.select_option("#repoSel", "acme/alpha")
    assert page.text_content("#qDefect").strip() == "50.0%"


# ---------------------------- empty states ----------------------------

def test_no_register_anywhere_reads_a_dash_not_zero(page, server):
    """'–' means 「未設定」. A measured 0.0% would claim the team shipped a
    window with no defects, which is a different and much stronger claim."""
    data = _load_fixture()
    del data["repo_meta"]["acme/alpha"]["defects"]
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#qDefect").strip() == "–"
    assert "defect_file" in dash.text_content("#qDefectSub")


def test_a_register_with_nothing_found_in_window_reads_zero(page, server):
    """0.0% is a real measurement and must be distinguishable from '–'."""
    data = _load_fixture()
    for item in data["repo_meta"]["acme/alpha"]["defects"]["items"]:
        item["found"] = "2019-01-01"
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#qDefect").strip() == "0.0%"


def test_truncation_is_declared_rather_than_passed_off_as_complete(page, server):
    data = _load_fixture()
    data["repo_meta"]["acme/alpha"]["defects"]["truncated"] = True
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert "截斷" in dash.text_content("#qDefectSub")


# ------------------------ the Defect 追蹤 table ------------------------

def test_register_entries_reach_the_defect_table(defect_page, server):
    """The table already merged issues and plan-file `#bug` items; the
    register is a third source, or it would stay empty as it is today."""
    page = open_dashboard(defect_page, server)
    body = page.inner_text("#defectRows")
    assert "匯出 CSV 中文亂碼" in body
    assert "資產統計金額用咗股數" in body


def test_the_table_shows_fixed_entries_as_fixed(defect_page, server):
    page = open_dashboard(defect_page, server)
    rows = page.eval_on_selector_all("#defectRows tr", "els => els.map(e => e.innerText)")
    fixed = [r for r in rows if "資產統計金額用咗股數" in r]
    assert fixed and "Fixed" in fixed[0]
