"""Unit tests for the 回退 / 補救 classifier in docs/js/aggregate.js.

Same in-browser technique as test_aggregate_js.py: there is no JS test runner
in this repo, so the ES module is imported inside a Playwright page and the
assertions are evaluated there. ?demo=1 lets the module resolve without the
private metrics.json.

What these pin is the *signal set*. The metric this feeds used to be a title
prefix test, /^(revert|hotfix)\\b/, which was wrong in both directions:

  - `hotfix` as a prefix was effectively dead code. Real hotfix commits are
    titled `fix: hotfix v2.6.0 — 21 bug fixes` (prefix `fix`), and hotfix work
    is identified by its branch, not its subject line.
  - `revert` as a prefix swept in churn that never reached production —
    reverting a docs commit, a dependency bump, or a mistaken branch merge.

Run:  python -m pytest scripts/test_remediation_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="remediation classifier tests need pytest-playwright")


def classify(page, server, tasks: list[dict]) -> list[bool]:
    """Return isRemediation() for each task, evaluated inside the page."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async (tasks) => { const m = await import('/js/aggregate.js'); "
        "return tasks.map(t => m.isRemediation(t)); }",
        tasks,
    )


def one(page, server, **task) -> bool:
    return classify(page, server, [task])[0]


# ------------------------- signals that DO count -------------------------

def test_own_revert_commit_counts(page, server):
    assert one(page, server, title="revert(ios-webauthn): restore passkey mode",
               branch="main") is True


def test_github_generated_revert_counts(page, server):
    """GitHub writes `Revert "<subject of the reverted commit>"`."""
    assert one(page, server, title='Revert "fix role manage ui issue"',
               branch="main") is True


def test_hotfix_branch_counts_even_when_the_title_says_nothing(page, server):
    """The signal the old prefix test missed entirely.

    46 of 979 tasks in the operator's 90-day window sat on hotfix/v2.6.1 with
    subjects like this one; exactly 3 were caught by the prefix regex.
    """
    assert one(page, server, title="fix 交易查詢 - 結算淨額",
               branch="hotfix/v2.6.1") is True


def test_patch_and_bugfix_branches_count_too(page, server):
    """hotfix/ is not the only remediation branch convention in use."""
    assert classify(page, server, [
        {"title": "adjust totals", "branch": "patch/2.6.2"},
        {"title": "adjust totals", "branch": "bugfix/SC-3318"},
    ]) == [True, True]


def test_hotfix_in_the_subject_counts(page, server):
    """`fix: hotfix v2.6.0 …` — a real title from the operator's data."""
    assert one(page, server, title="fix: hotfix v2.6.0 — 21 bug fixes",
               branch="main") is True


def test_regression_in_the_subject_counts(page, server):
    assert one(page, server, title="Fix: Regression bug fix v2",
               branch="main") is True


def test_chinese_withdrawal_wording_counts(page, server):
    """撤回 / 回退 — the team writes some subjects in Chinese."""
    assert classify(page, server, [
        {"title": "fix:撤回", "branch": "main"},
        {"title": "回退 COALESCE 改動", "branch": "main"},
    ]) == [True, True]


# ----------------------- exceptions that do NOT count -----------------------

def test_reverting_a_docs_commit_does_not_count(page, server):
    assert one(page, server,
               title='Revert "docs: add force update & app maintenance design spec"',
               branch="Refactor") is False


def test_reverting_chore_style_test_ci_build_does_not_count(page, server):
    assert classify(page, server, [
        {"title": 'Revert "chore(android): add Fresco animated-gif dependency"', "branch": "main"},
        {"title": 'Revert "style(login-home): switch welcome text to white"', "branch": "main"},
        {"title": 'Revert "test: add snapshot for widget"', "branch": "main"},
        {"title": 'Revert "ci: pin the runner image"', "branch": "main"},
        {"title": 'Revert "build: bump gradle"', "branch": "main"},
    ]) == [False, False, False, False, False]


def test_reverting_a_mistaken_branch_merge_does_not_count(page, server):
    """Undoing a bad merge is version-control hygiene, not remediation."""
    assert one(
        page, server,
        title='Revert "Merge branch \'feature/business-details\' into feature/netcore"',
        branch="product-selection-update") is False


def test_an_exception_never_suppresses_an_independent_signal(page, server):
    """A non-shipping revert sitting ON a hotfix branch still counts.

    The exception list narrows the revert signal only. If it short-circuited
    the whole predicate, real hotfix work would be silently discarded — the
    operator's data has `Revert "WSL dev config: …"` on hotfix/v2.6.1.
    """
    assert one(page, server, title='Revert "docs: add design spec"',
               branch="hotfix/v2.6.1") is True


def test_ordinary_work_does_not_count(page, server):
    assert classify(page, server, [
        {"title": "feat: add checkout", "branch": "main"},
        {"title": "fix: widget crash on cold start", "branch": "main"},
        {"title": "chore: bump deps", "branch": "feature/x"},
        {"title": "refactor: extract fee calculator", "branch": "Refactor"},
    ]) == [False, False, False, False]


def test_missing_title_and_branch_are_tolerated(page, server):
    """collect_github.py can emit a task with neither field populated."""
    assert classify(page, server, [
        {}, {"title": None, "branch": None}, {"title": "", "branch": ""},
    ]) == [False, False, False]


# --------------------------- the counter it feeds ---------------------------

def test_stats_from_tasks_counts_remedy_tasks(page, server):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    tasks = [
        {"kind": "commit", "title": 'Revert "feat: add checkout"', "branch": "main"},
        {"kind": "commit", "title": "fix 交易查詢", "branch": "hotfix/v2.6.1"},
        {"kind": "commit", "title": 'Revert "docs: add spec"', "branch": "main"},
        {"kind": "pr", "title": "feat: add checkout", "branch": "main"},
    ]
    got = page.evaluate(
        "async (tasks) => { const m = await import('/js/aggregate.js'); "
        "const s = m.statsFromTasks(tasks); "
        "return {remedyTasks: s.remedyTasks, total: s.total}; }",
        tasks,
    )
    # 2 remedy of 4 tasks; the docs revert is excluded. total counts untagged
    # tasks too, so both sides of the ratio span the same set.
    assert got == {"remedyTasks": 2, "total": 4}


def test_remedy_tasks_never_exceeds_total(page, server):
    """The invariant the old metric could not hold: it divided task counts by
    git tag counts and needed Math.min(…, 100) to stay plausible."""
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    cases = [
        [],
        [{"kind": "commit", "title": 'Revert "x"', "branch": "hotfix/v1"}],
        [{"kind": "commit", "title": "fix: hotfix regression 撤回", "branch": "hotfix/v1"}],
        [{"kind": "pr", "title": "feat: a", "branch": "main"}],
    ]
    got = page.evaluate(
        "async (cases) => { const m = await import('/js/aggregate.js'); "
        "return cases.map(ts => { const s = m.statsFromTasks(ts); "
        "return s.remedyTasks <= s.total; }); }",
        cases,
    )
    assert got == [True] * len(cases)
