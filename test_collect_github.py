"""Tests for collect_github.py — GitHub API mocked, no network required.

Run:  pytest scripts/test_collect_github.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from collect_github import (  # noqa: E402
    DEFAULT_CLASSIFY,
    CollectError,
    classify,
    collect_commits,
    collect_prs,
    load_config,
    normalize_level,
)

CFG = DEFAULT_CLASSIFY
SINCE = "2026-04-01T00:00:00+00:00"


class FakeClient:
    """Returns canned GraphQL responses in call order."""

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def graphql(self, query: str, variables: dict) -> dict:
        self.calls.append(variables)
        return self.responses.pop(0)


def commit_node(sha="abc1234", message="feat: x", author_login="wing",
                parents=1, prs=0, date="2026-05-01T10:00:00Z", add=10):
    return {
        "abbreviatedOid": sha,
        "committedDate": date,
        "message": message,
        "additions": add,
        "deletions": 2,
        "url": f"https://github.com/wing/abci/commit/{sha}",
        "parents": {"totalCount": parents},
        "author": {"name": "Wing", "user": {"login": author_login} if author_login else None},
        "associatedPullRequests": {"totalCount": prs},
    }


def commits_page(nodes, has_next=False, cursor=None):
    return {"repository": {"object": {"history": {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": nodes,
    }}}}


def pr_node(number=1, title="feat: y", body="", labels=(), author="wing",
            merged="2026-05-02T10:00:00Z", updated=None, add=50):
    return {
        "number": number,
        "title": title,
        "body": body,
        "mergedAt": merged,
        "updatedAt": updated or merged,
        "additions": add,
        "deletions": 5,
        "url": f"https://github.com/wing/abci/pull/{number}",
        "author": {"login": author},
        "labels": {"nodes": [{"name": l} for l in labels]},
    }


def prs_page(nodes, has_next=False, cursor=None):
    return {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": nodes,
    }}}


# ---------------------------------------------------------------- classify

@pytest.mark.parametrize("raw,expected", [
    ("L3", "L3"), ("l4", "L4"), ("5", "L5"), ("L9", None), ("high", None),
])
def test_normalize_level(raw, expected):
    assert normalize_level(raw) == expected


def test_label_beats_trailer():
    level, method = classify(
        CFG, labels=("ai-level/L4",), text="feat: x\n\nAI-Level: L2"
    )
    assert (level, method) == ("L4", "label")


def test_trailer_in_commit_message():
    level, method = classify(CFG, text="fix: bug\n\nsome body\n\nAI-Level: l3")
    assert (level, method) == ("L3", "trailer")


def test_trailer_beats_heuristic_rule():
    text = "feat: x\n\nAI-Level: L2\nCo-Authored-By: Claude <noreply@anthropic.com>"
    assert classify(CFG, text=text) == ("L2", "trailer")


def test_claude_code_footer_rule():
    text = "feat: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
    assert classify(CFG, text=text) == ("L3", "rule")


def test_author_mapping_beats_rules():
    cfg = {**CFG, "author_levels": {"my-agent[bot]": "L5"}}
    text = "feat: x\n\nCo-Authored-By: Claude"
    assert classify(cfg, text=text, author="my-agent[bot]") == ("L5", "author")


def test_no_match_returns_none():
    assert classify(CFG, text="chore: bump deps") == (None, None)


# ---------------------------------------------------------------- commits

def test_collect_commits_paginates_and_filters():
    client = FakeClient([
        commits_page(
            [
                commit_node(sha="aaa1111", message="feat: a\n\nAI-Level: L3"),
                commit_node(sha="bbb2222", parents=2),                # merge → skip
                commit_node(sha="ccc3333", author_login="dependabot[bot]"),  # excluded
            ],
            has_next=True, cursor="C1",
        ),
        commits_page([
            commit_node(sha="ddd4444", prs=1),                        # PR-associated → skip (auto)
            commit_node(sha="eee5555", message="docs: readme"),       # untagged, kept
        ]),
    ])
    tasks = collect_commits(client, "wing/abci", "main", SINCE, CFG, skip_pr_commits=True)
    assert [t.id for t in tasks] == ["aaa1111", "eee5555"]
    assert tasks[0].level == "L3" and tasks[0].method == "trailer"
    assert tasks[1].level is None
    assert client.calls[1]["cursor"] == "C1"  # second page requested with cursor


def test_collect_commits_keeps_pr_commits_in_commits_mode():
    client = FakeClient([commits_page([commit_node(sha="ddd4444", prs=1)])])
    tasks = collect_commits(client, "wing/abci", "main", SINCE, CFG, skip_pr_commits=False)
    assert [t.id for t in tasks] == ["ddd4444"]


def test_collect_commits_missing_branch_raises():
    client = FakeClient([{"repository": {"object": None}}])
    with pytest.raises(CollectError, match="branch 'main' not found"):
        collect_commits(client, "wing/abci", "main", SINCE, CFG, skip_pr_commits=True)


# ---------------------------------------------------------------- PRs

def test_collect_prs_label_and_window_filter():
    client = FakeClient([prs_page([
        pr_node(number=10, labels=("ai-level/L4",), merged="2026-05-02T10:00:00Z"),
        pr_node(number=9, merged="2026-03-01T10:00:00Z", updated="2026-05-01T10:00:00Z"),  # merged pre-window
    ])])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert [t.id for t in tasks] == ["10"]
    assert tasks[0].level == "L4" and tasks[0].method == "label" and tasks[0].kind == "pr"


def test_collect_prs_stops_when_page_is_stale():
    client = FakeClient([
        prs_page([pr_node(number=3, merged="2026-02-01T00:00:00Z",
                          updated="2026-02-02T00:00:00Z")], has_next=True, cursor="P1"),
        prs_page([pr_node(number=2)]),  # must never be requested
    ])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert len(client.calls) == 1  # early stop — no second page fetch


def test_collect_prs_trailer_in_body():
    client = FakeClient([prs_page([pr_node(number=7, body="details...\n\nAI-Level: 5")])])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L5" and tasks[0].method == "trailer"


# ---------------------------------------------------------------- config

def test_load_config_merges_defaults(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'window_days = 90\n[[repos]]\nname = "wing/abci"\n'
        '[classify]\nlabel_prefix = "lvl:"\n'
    )
    cfg = load_config(cfg_file)
    assert cfg["window_days"] == 90
    assert cfg["mode"] == "auto"
    assert cfg["classify"]["label_prefix"] == "lvl:"
    assert cfg["classify"]["trailer_key"] == "AI-Level"  # default kept


def test_load_config_requires_repos(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("window_days = 90\n")
    with pytest.raises(CollectError, match="no \\[\\[repos\\]\\]"):
        load_config(cfg_file)
