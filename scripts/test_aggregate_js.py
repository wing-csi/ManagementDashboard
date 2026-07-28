"""Unit tests for docs/js/aggregate.js, executed in a real browser.

There is no JS test runner in this repo (no package.json), so pure frontend
logic is exercised by importing the ES module inside a Playwright page and
evaluating assertions there. The page is loaded with ?demo=1 so the module
resolves against a same-origin document without needing the private
metrics.json.

Run:  python -m pytest scripts/test_aggregate_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="aggregate.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    """Import aggregate.js in the page and return the value of `body`."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/aggregate.js'); "
        f"return ({body}); }}"
    )


def test_stats_from_tasks_normal_data_with_reviews_and_rework(page, server):
    """Test normal data: 3 reviewed PRs, 2 with rework > 0."""
    got = evaluate(page, server, """
        (() => {
          const tasks = [
            {kind: 'pr', reviewed: true, rework: 0, rework_hours: null, additions: 10},
            {kind: 'pr', reviewed: true, rework: 2, rework_hours: 4.5, additions: 10},
            {kind: 'pr', reviewed: true, rework: 1, rework_hours: 2.0, additions: 10},
          ];
          const s = m.statsFromTasks(tasks);
          return {
            reviewedPRs: s.reviewedPRs,
            reworkPRs: s.reworkPRs,
            reworkRounds: s.reworkRounds,
            reworkTurnarounds: s.reworkTurnarounds,
          };
        })()
    """)
    assert got == {
        "reviewedPRs": 3,
        "reworkPRs": 2,
        "reworkRounds": [2, 1],
        "reworkTurnarounds": [4.5, 2.0],
    }


def test_stats_from_tasks_legacy_data_no_reviewed_field(page, server):
    """Test legacy data: PRs with rework > 0 but NO reviewed key.

    Without the structural nesting, this case would give reworkPRs=2, reviewedPRs=0,
    violating the invariant. With the fix, both should be 0.
    """
    got = evaluate(page, server, """
        (() => {
          const tasks = [
            {kind: 'pr', rework: 2, rework_hours: 3.0, additions: 10},
            {kind: 'pr', rework: 1, rework_hours: 1.5, additions: 10},
          ];
          const s = m.statsFromTasks(tasks);
          return {
            reviewedPRs: s.reviewedPRs,
            reworkPRs: s.reworkPRs,
            invariantHolds: s.reworkPRs <= s.reviewedPRs,
            reworkRounds: s.reworkRounds,
            reworkTurnarounds: s.reworkTurnarounds,
          };
        })()
    """)
    assert got == {
        "reviewedPRs": 0,
        "reworkPRs": 0,
        "invariantHolds": True,
        "reworkRounds": [],
        "reworkTurnarounds": [],
    }


def test_stats_from_tasks_rework_hours_zero_is_admitted(page, server):
    """Test that rework_hours of 0 is admitted into reworkTurnarounds."""
    got = evaluate(page, server, """
        (() => {
          const tasks = [
            {kind: 'pr', reviewed: true, rework: 1, rework_hours: 0, additions: 10},
            {kind: 'pr', reviewed: true, rework: 1, rework_hours: null, additions: 10},
          ];
          const s = m.statsFromTasks(tasks);
          return {
            reworkPRs: s.reworkPRs,
            reworkRounds: s.reworkRounds,
            reworkTurnarounds: s.reworkTurnarounds,
          };
        })()
    """)
    assert got == {
        "reworkPRs": 2,
        "reworkRounds": [1, 1],
        "reworkTurnarounds": [0],  # 0 is included, null is excluded
    }


def test_stats_from_tasks_commits_never_contribute(page, server):
    """Test that commits (kind: 'commit') never contribute to any counter."""
    got = evaluate(page, server, """
        (() => {
          const tasks = [
            {kind: 'commit', reviewed: true, rework: 2, rework_hours: 5.0, additions: 10},
            {kind: 'pr', reviewed: true, rework: 1, rework_hours: 2.0, additions: 10},
          ];
          const s = m.statsFromTasks(tasks);
          return {
            reviewedPRs: s.reviewedPRs,
            reworkPRs: s.reworkPRs,
            reworkRounds: s.reworkRounds,
            reworkTurnarounds: s.reworkTurnarounds,
          };
        })()
    """)
    assert got == {
        "reviewedPRs": 1,
        "reworkPRs": 1,
        "reworkRounds": [1],
        "reworkTurnarounds": [2.0],
    }


def test_stats_from_tasks_invariant_always_holds(page, server):
    """Test the critical invariant: reworkPRs <= reviewedPRs always."""
    got = evaluate(page, server, """
        (() => {
          const testCases = [
            [],
            [{kind: 'pr', reviewed: true, rework: 0, additions: 10}],
            [{kind: 'pr', reviewed: false, rework: 2, additions: 10}],
            [{kind: 'pr', reviewed: true, rework: 3, additions: 10}],
            [{kind: 'pr', reviewed: true, additions: 10}, {kind: 'pr', reviewed: false, additions: 10}],
          ];
          return testCases.map(tasks => {
            const s = m.statsFromTasks(tasks);
            return s.reworkPRs <= s.reviewedPRs;
          });
        })()
    """)
    assert got == [True, True, True, True, True]
