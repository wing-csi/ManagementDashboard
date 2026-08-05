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
        {"rework": 2},
        {"ci": "fail"},
        {},
    ]
    statuses = ["redline", "warning", "suspect", "rework", "ci-fail"]
    assert classify(page, server, tasks, statuses) == [
        [True, False, False, False, False, False, False],
        [False, True, True, False, False, False, False],
        [False, False, False, True, False, False, False],
        [False, False, False, False, True, False, False],
        [False, False, False, False, False, True, False],
    ]


def test_all_status_keeps_every_task(page, server):
    tasks = [{}, {"violations": ["direct-push-main"]}, {"ci": "fail"}]
    assert classify(page, server, tasks, ["all"]) == [[True, True, True]]
