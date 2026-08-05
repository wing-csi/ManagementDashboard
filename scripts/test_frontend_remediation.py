"""Behaviour tests for the 回退密度 card that replaced 變更失敗率(proxy).

The old card computed `revert/hotfix tasks ÷ deployment events`. That is not a
ratio: the numerator counted commits and the denominator counted git tags, so
one failed release producing five revert commits scored as five failures, and
the result had to be clamped with Math.min(…, 100) to stay under 100%. On the
operator's real data it read 72% — off the bottom of the DORA scale, where a
low performer sits at 46–60%.

回退密度 divides remediation tasks by all tasks in the same window and scope.
Both sides are tasks, so the value is a real proportion, it needs no clamp,
and it stays meaningful under a person filter — which the old metric could not
do, because one person's reverts over the whole repo's deployments is not a
rate.

The fixture is served by intercepting the metrics.json request rather than
swapping docs/data/metrics.json on disk, which holds the operator's real
private data. Same reasoning as test_frontend_rework.py.

Run:  python -m pytest scripts/test_frontend_remediation.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="回退密度 tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-remediation.json"


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
def remedy_page(page):
    _serve(page, _load_fixture())
    return page


def open_dashboard(remedy_page, server, query: str = ""):
    remedy_page.goto(f"{server}/{query}", wait_until="networkidle")
    # state="attached": #taskRows lives in the Tasks panel, hidden until selected.
    remedy_page.wait_for_selector("#taskRows tr", state="attached")
    return remedy_page


# ------------------------------ the ratio itself ------------------------------

def test_density_is_remedy_tasks_over_all_tasks(remedy_page, server):
    """5 remediation of 10 tasks.

    Counted: the revert of a shipped feature, the hotfix-branch commit, the
    `fix: hotfix v2.6.0` subject, the regression fix, and 撤回.
    Not counted: reverts of a docs commit, a dependency bump, and a mistaken
    branch merge.
    """
    page = open_dashboard(remedy_page, server)
    assert page.text_content("#dCfr").strip() == "50%"


def test_subtext_shows_both_sides_of_the_ratio(remedy_page, server):
    page = open_dashboard(remedy_page, server)
    assert "5 / 10" in page.text_content("#dCfrSub")


def test_it_renders_with_no_deployment_records_at_all(remedy_page, server):
    """The regression guard.

    The fixture has empty deployments, releases and tags — the operator's real
    state for 12 of 14 repos. The old metric divided by those, so it rendered
    '–' unless another repo's tag count happened to stand in as the
    denominator. 回退密度 does not depend on them.
    """
    data = _load_fixture()
    assert data["repo_meta"]["acme/alpha"]["deployments"] == []
    assert data["repo_meta"]["acme/alpha"]["tags"] == []
    assert data["repo_meta"]["acme/alpha"]["releases"] == []
    page = open_dashboard(remedy_page, server)
    assert page.text_content("#dCfr").strip() == "50%"


def test_the_card_is_no_longer_labelled_a_failure_rate(remedy_page, server):
    """A proportion of remediation work is not a change failure rate, and
    labelling it one invites comparison against the DORA benchmark."""
    page = open_dashboard(remedy_page, server)
    strip = page.inner_html(".dora-strip")
    assert "失敗率" not in strip
    assert "回退密度" in strip


# ------------------------------ person scoping ------------------------------

def test_density_holds_under_a_person_filter(remedy_page, server):
    """Wing: 1 remediation (the feature revert) of 5 tasks.
    Tony: 4 of 5. Both sides are person-scoped, so the ratio is valid."""
    page = open_dashboard(remedy_page, server)
    page.select_option("#personSel", "Wing")
    assert page.text_content("#dCfr").strip() == "20%"
    page.select_option("#personSel", "Tony")
    assert page.text_content("#dCfr").strip() == "80%"


def test_person_subtext_reports_the_person_scoped_counts(remedy_page, server):
    page = open_dashboard(remedy_page, server)
    page.select_option("#personSel", "Tony")
    assert "4 / 5" in page.text_content("#dCfrSub")


# -------------------------------- edge cases --------------------------------

def test_no_clamp_is_needed_when_every_task_is_remediation(page, server):
    """100% is reachable and correct; it is not a clamped artefact."""
    data = _load_fixture()
    for t in data["tasks"]:
        t["branch"] = "hotfix/v2.6.1"
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#dCfr").strip() == "100%"


def test_zero_remediation_reads_zero_not_a_dash(page, server):
    """A measured 0% is real information and must not be blanked."""
    data = _load_fixture()
    data["tasks"] = [t for t in data["tasks"]
                     if t["title"] == "feat: add checkout"]
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#dCfr").strip() == "0%"


def test_empty_scope_reads_a_dash(page, server):
    """No tasks means no denominator — '–', distinct from a measured 0%.

    Loaded without waiting for #taskRows: with an empty window there are no
    rows to wait for. The subtext assertion is what proves renderDora actually
    ran, rather than the '–' being the untouched markup default.
    """
    data = _load_fixture()
    data["tasks"] = [dict(t, date="2019-01-01") for t in data["tasks"]]
    _serve(page, data)
    page.goto(f"{server}/", wait_until="networkidle")
    assert page.text_content("#dCfr").strip() == "–"
    assert "無工作" in page.text_content("#dCfrSub")
