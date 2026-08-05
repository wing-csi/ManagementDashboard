"""Behaviour tests for the corrected rework statistics.

The fixture is served by intercepting the metrics.json request, NOT by
swapping docs/data/metrics.json on disk — that file holds the operator's real
private data locally, and an interrupted swap-pattern run leaves a small test
fixture where it used to be. Same reasoning as test_frontend_people.py.

metrics-fixture.json and rendered-baseline.json are deliberately untouched:
their value is proving the *default* render did not shift.

Run:  python -m pytest scripts/test_frontend_rework.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="rework statistics tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-rework.json"


@pytest.fixture()
def rework_page(page):
    """A page that receives the rework fixture in place of metrics.json."""
    body = FIXTURE.read_text(encoding="utf-8")
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=body),
    )
    return page


def open_dashboard(rework_page, server, query: str = ""):
    rework_page.goto(f"{server}/{query}", wait_until="networkidle")
    # state="attached": #taskRows sits in the Tasks panel, hidden until selected.
    # The quality cards these tests assert on are read with text_content(), which
    # works on hidden elements — only the readiness wait needed changing.
    rework_page.wait_for_selector("#taskRows tr", state="attached")
    return rework_page


def test_rework_rate_denominator_excludes_unreviewed_prs(rework_page, server):
    page = open_dashboard(rework_page, server)
    # 2 rejected of 3 reviewed = 66.7%, NOT 2 of 4 merged = 50%.
    assert "66.7" in page.text_content("#qRework")


def test_rework_subtext_reports_reviewed_count_and_median_rounds(rework_page, server):
    page = open_dashboard(rework_page, server)
    sub = page.text_content("#qReworkSub")
    assert "2 / 3" in sub
    assert "1.5" in sub


def test_turnaround_card_shows_median_hours(rework_page, server):
    page = open_dashboard(rework_page, server)
    # median of [48, 12] = 30 hours; fmtHours renders <48h as hours.
    assert "30.0" in page.text_content("#qTurn")


def test_accept_rate_blanks_out_under_a_person_filter(rework_page, server):
    page = open_dashboard(rework_page, server, "?owner=Wing")
    # Person-scoped merges ÷ repo-wide closed PRs is not a rate.
    assert page.text_content("#qAccept").strip() == "–"


def test_accept_rate_still_renders_for_everyone(rework_page, server):
    page = open_dashboard(rework_page, server)
    assert page.text_content("#qAccept").strip() != "–"


# ------------- edge cases in the reviewed/rework/turnaround empty states -------------
#
# These use `page` directly rather than the `rework_page` fixture: each test needs its
# own variant of the fixture data, built by loading the pinned JSON and mutating a copy
# (same pattern as test_frontend_people.py::test_contributors_are_not_truncated), not by
# editing metrics-fixture-rework.json itself — that file pins the arithmetic the five
# tests above assert.

def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def test_rework_sub_omits_median_when_no_reviewed_pr_was_rejected(page, server):
    """reworkRounds is [] when every reviewed PR is clean; median([]) is null,
    and the subtext must not interpolate the literal string "null"."""
    data = _load_fixture()
    for t in data["tasks"]:
        t["rework"] = 0
        t["rework_hours"] = None
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert "null" not in dash.text_content("#qReworkSub")
    assert dash.text_content("#qRework").strip().startswith("0.0")


def test_turn_sub_distinguishes_no_measurable_turnaround_from_no_rejection(page, server):
    """rework > 0 with rework_hours all null is a real by-design state (the
    first rejection landed at/after merge) — it must not be reported as if
    nothing was rejected."""
    data = _load_fixture()
    for t in data["tasks"]:
        t["rework_hours"] = None
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert "無被打回" not in dash.text_content("#qTurnSub")
    assert dash.text_content("#qTurn").strip() == "–"


def test_rework_sub_reports_no_prs_when_scope_has_none(page, server):
    data = _load_fixture()
    for t in data["tasks"]:
        t["kind"] = "commit"
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#qReworkSub").strip() == "此範圍內無 PR"


def test_rework_card_reads_dash_when_every_pr_is_unreviewed(page, server):
    """Middle empty state: PRs exist but none of them received a human review,
    so reviewedPRs is 0. This must read '–' with the un-reviewed message —
    distinct from both '此範圍內無 PR' (no PRs at all, tested above) and from
    an actual 0%, which would wrongly claim a measured rate of zero rework."""
    data = _load_fixture()
    for t in data["tasks"]:
        t["reviewed"] = False
    _serve(page, data)
    dash = open_dashboard(page, server)
    assert dash.text_content("#qRework").strip() == "–"
    assert "此範圍內無經審核的 PR" in dash.text_content("#qReworkSub")
