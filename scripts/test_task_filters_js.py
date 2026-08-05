"""Unit tests for the Task tab's status classifier."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="task filter tests need pytest-playwright")


def classify(page, server, tasks: list[dict], statuses: list[str]) -> list[list[bool]]:
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async ([tasks, statuses]) => { "
        "const m = await import('/js/render-table.js'); "
        "return statuses.map(s => tasks.map(t => m.taskMatchesStatus(t, s))); }",
        [tasks, statuses],
    )


def test_each_status_uses_its_own_task_signal(page, server):
    tasks = [
        {"violations": ["direct-push-main"]},
        {"violations": ["oversized-pr"]},
        {"violations": ["future-warning"]},
        {"check": "suspect:human-gates-observed"},
        {"ci": "fail"},
        {},
    ]
    statuses = ["redline", "warning", "suspect", "ci-fail"]
    assert classify(page, server, tasks, statuses) == [
        [True, False, False, False, False, False],
        [False, True, True, False, False, False],
        [False, False, False, True, False, False],
        [False, False, False, False, True, False],
    ]


def test_all_status_keeps_every_task(page, server):
    tasks = [{}, {"violations": ["direct-push-main"]}, {"ci": "fail"}]
    assert classify(page, server, tasks, ["all"]) == [[True, True, True]]


def test_task_pr_context_is_explicit_for_prs_and_direct_commits(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    got = page.evaluate(
        "async () => { "
        "const m = await import('/js/render-table.js'); "
        "const inspect = (task) => { "
        "  const host = document.createElement('div'); "
        "  host.innerHTML = m.taskPullRequestMarkup(task); "
        "  return {text: host.textContent.trim(), links: [...host.querySelectorAll('a')].map(a => a.textContent)}; "
        "}; "
        "return ["
        "  inspect({kind: 'pr', id: '42', url: 'https://example.test/pr/42'}), "
        "  inspect({kind: 'commit', id: 'abc1234', url: 'https://example.test/commit/abc1234'})"
        "]; }"
    )
    assert got == [
        {"text": "#42", "links": ["#42"]},
        {"text": "無 PRabc1234", "links": ["abc1234"]},
    ]
