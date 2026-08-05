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

import json
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
    # state="attached": #taskRows sits in the Tasks panel, hidden until selected.
    people_page.wait_for_selector("#taskRows tr", state="attached")
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


# ---------------- person-scoped and team-wide sections ----------------

def test_remediation_density_narrows_with_the_person_filter(people_page, server):
    """回退密度 replaced 變更失敗率(proxy), which had to blank out here.

    The old metric divided one person's reverts by the whole repo's deployment
    count — numerator and denominator on different scopes, so not a rate, and
    the card read '–' the moment a person was picked. 回退密度 is tasks ÷ tasks,
    so the filter narrows both sides together and the value stays meaningful.

    Fixture: `revert: beta one` is the only remediation task of 4 team-wide;
    Wing's two tasks are both ordinary work. test_frontend_remediation.py
    covers the classifier and the arithmetic in depth.
    """
    page = open_dashboard(people_page, server)
    assert page.text_content("#dCfr").strip() == "25%"
    page.select_option("#personSel", "Wing")
    assert page.text_content("#dCfr").strip() == "0%"


def test_contributors_stay_team_wide(people_page, server):
    """It is the comparison view and the place you pick a person from."""
    page = open_dashboard(people_page, server)
    page.select_option("#personSel", "Wing")
    names = page.eval_on_selector_all(
        "#ovContribs .contrib .nm span[title]", "els => els.map(e => e.title)")
    assert "Tony" in names and "Wing" in names
    assert page.eval_on_selector_all(
        "#ovContribs .contrib.is-selected", "els => els.length") == 1


def test_contributors_are_not_truncated(page, server):
    """A nine-person window renders nine cards, each a % of the whole window.

    Its own fixture: the shared one has two people, so it cannot tell a
    full list apart from a top-N cut. Nine equal contributors also pin the
    percentage denominator — a top-6 cut would read 16.7%, not 11.1%.
    """
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    proto = data["tasks"][0]
    data["people"] = {}
    data["tasks"] = [
        {**proto, "id": str(i), "url": f"https://example.test/{i}",
         "author": f"dev{i:02d}"}
        for i in range(1, 10)
    ]
    page.route("**/data/metrics.json", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(data, ensure_ascii=False)))

    open_dashboard(page, server)
    names = page.eval_on_selector_all(
        "#ovContribs .contrib .nm span[title]", "els => els.map(e => e.title)")
    assert sorted(names) == [f"dev{i:02d}" for i in range(1, 10)]

    pcts = page.eval_on_selector_all(
        "#ovContribs .contrib .pc", "els => els.map(e => e.textContent)")
    assert all(p.strip().endswith("11.1%") for p in pcts), pcts


def test_scope_notes_appear_only_when_filtered(people_page, server):
    page = open_dashboard(people_page, server)
    visible = "els => els.filter(e => !e.hidden).length"
    assert page.eval_on_selector_all(".scope-note", visible) == 0
    page.select_option("#personSel", "Wing")
    assert page.eval_on_selector_all(".scope-note", visible) > 0


def test_eyebrow_names_the_filtered_person(people_page, server):
    page = open_dashboard(people_page, server)
    page.select_option("#personSel", "Wing")
    assert "Wing" in page.text_content("#eyebrow")


def test_owner_optgroup_lists_declared_owners(people_page, server):
    page = open_dashboard(people_page, server)
    values = page.eval_on_selector_all(
        "#repoSel option", "els => els.map(e => e.value)")
    assert "owner:Wing" in values
    assert page.eval_on_selector_all("#repoSel optgroup", "els => els.length") == 2


def test_owner_selection_scopes_to_that_owners_repos(people_page, server):
    page = open_dashboard(people_page, server)
    page.select_option("#repoSel", "owner:Wing")
    repos = page.eval_on_selector_all(
        "#taskRows tr td:nth-child(2)", "els => els.map(e => e.textContent.trim())")
    assert set(repos) == {"alpha"}          # acme/beta has no owner


def test_owner_selection_disables_branch_select(people_page, server):
    """Branch names are not comparable across repos, same as 全部 repos."""
    page = open_dashboard(people_page, server)
    page.select_option("#repoSel", "owner:Wing")
    assert page.is_disabled("#branchSel")


def test_owner_chip_shows_on_project_progress(people_page, server):
    page = open_dashboard(people_page, server)
    # state="attached": #projChips sits in the 項目 & 團隊 panel, hidden on load.
    page.wait_for_selector("#projChips .chip-rag", state="attached")
    text = page.text_content("#projChips")
    assert "Wing" in text and "未指定" in text


def test_rag_ignores_the_person_filter(people_page, server):
    """repoRag() calls windowTasks(); without pinning, its CI pass rate would
    silently become one person's PRs while coverage stays repo-wide."""
    page = open_dashboard(people_page, server)
    before = page.inner_html("#ragRow")
    page.select_option("#personSel", "Wing")
    assert page.inner_html("#ragRow") == before
