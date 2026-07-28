"""Behaviour tests for the contributor filter.

Two deliberate choices here:

1. The fixture is served by intercepting the metrics.json request, NOT by
   swapping docs/data/metrics.json on disk. That file holds the operator's
   real (private) data locally, so an interrupted run using the swap pattern
   leaves a 2 KB test fixture where 1.2 MB of real data used to be, and the
   next run then "restores" the fixture as if it were the original.
2. metrics-fixture.json and rendered-baseline.json are left alone — their
   value is proving the *default* render did not shift, so this module gets
   its own fixture.

Run:  python -m pytest scripts/test_frontend_people.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="contributor filter tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-people.json"


@pytest.fixture()
def people_page(page):
    """A page that receives the people fixture in place of metrics.json."""
    body = FIXTURE.read_text(encoding="utf-8")
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=body),
    )
    return page


def open_dashboard(people_page, server, query: str = ""):
    people_page.goto(f"{server}/{query}", wait_until="networkidle")
    people_page.wait_for_selector("#taskRows tr")
    return people_page


def authors_in_table(page) -> list[str]:
    return page.eval_on_selector_all(
        "#taskRows tr td:nth-child(3)", "els => els.map(e => e.textContent.trim())")


def test_person_options_merge_aliases(people_page, server):
    page = open_dashboard(people_page, server)
    labels = page.eval_on_selector_all(
        "#personSel option", "els => els.map(e => e.textContent.trim())")
    assert labels[0].startswith("全部")
    # Wing = wing-csi + wing2036 = 2 tasks; Tony = 2 tasks
    assert "Wing (2)" in labels and "Tony (2)" in labels
    assert "wing2036" not in " ".join(labels)


def test_selecting_person_includes_aliased_tasks(people_page, server):
    page = open_dashboard(people_page, server)
    page.select_option("#personSel", "Wing")
    assert sorted(authors_in_table(page)) == ["wing-csi", "wing2036"]


def test_owner_url_param_applies_on_load(people_page, server):
    page = open_dashboard(people_page, server, "?owner=Wing")
    assert page.input_value("#personSel") == "Wing"
    assert sorted(authors_in_table(page)) == ["wing-csi", "wing2036"]


def test_selection_is_written_to_the_url(people_page, server):
    page = open_dashboard(people_page, server)
    page.select_option("#personSel", "Tony")
    assert "owner=Tony" in page.url
    page.select_option("#personSel", "all")
    assert "owner=" not in page.url


@pytest.mark.parametrize("bad", ["nobody", "<img src=x onerror=alert(1)>"])
def test_unknown_owner_param_falls_back_without_injecting(people_page, server, bad):
    """?owner= is untrusted: compared against the known list, never rendered."""
    page = open_dashboard(people_page, server, f"?owner={bad}")
    assert page.input_value("#personSel") == "all"
    assert page.is_hidden("#loadError")
    assert len(authors_in_table(page)) == 4
    assert page.eval_on_selector("#personSel", "el => el.querySelector('img')") is None


def test_switching_repo_resets_a_person_with_no_tasks(people_page, server):
    page = open_dashboard(people_page, server)
    page.select_option("#personSel", "Wing")
    page.select_option("#repoSel", "acme/beta")   # Wing has no tasks here
    assert page.input_value("#personSel") == "all"
