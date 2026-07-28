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
    rework_page.wait_for_selector("#taskRows tr")
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
