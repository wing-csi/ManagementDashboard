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
            author_type="User", merged="2026-05-02T10:00:00Z", updated=None, add=50,
            commits=(), merged_by=("wing", "User"), auto_merge=False, reviews=(),
            threads=0, files=()):
    return {
        "number": number,
        "title": title,
        "body": body,
        "mergedAt": merged,
        "updatedAt": updated or merged,
        "additions": add,
        "deletions": 5,
        "url": f"https://github.com/wing/abci/pull/{number}",
        "author": {"login": author, "__typename": author_type},
        "mergedBy": {"login": merged_by[0], "__typename": merged_by[1]},
        "autoMergeRequest": {"enabledBy": {"login": "agent"}} if auto_merge else None,
        "reviews": {"nodes": [
            {"state": st, "author": {"login": lg, "__typename": tp}}
            for (st, lg, tp) in reviews
        ]},
        "reviewThreads": {"totalCount": threads},
        "labels": {"nodes": [{"name": l} for l in labels]},
        "commits": {"nodes": [{"commit": {"message": m}} for m in commits]},
        "files": {"nodes": [{"path": p} for p in files]},
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


def test_collect_prs_trailer_in_inner_commit():
    client = FakeClient([prs_page([
        pr_node(number=8, commits=("feat: x\n\nAI-Level: L4",)),
    ])])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L4" and tasks[0].method == "trailer"


def test_collect_prs_claude_footer_classified_by_inference():
    footer = "feat: z\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\nCo-Authored-By: Claude <noreply@anthropic.com>"
    client = FakeClient([prs_page([pr_node(number=9, commits=(footer,))])])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L3" and tasks[0].method.startswith("inference:")


def test_collect_prs_label_beats_inner_commit_signals():
    client = FakeClient([prs_page([
        pr_node(number=10, labels=("ai-level/L2",),
                commits=("feat: y\n\nAI-Level: L4\nCo-Authored-By: Claude",)),
    ])])
    tasks = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L2" and tasks[0].method == "label"


# ------------------------------------------------------------ inference

CLAUDE_FOOTER = (
    "feat: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
    "Co-Authored-By: Claude <noreply@anthropic.com>"
)


def infer_one(cfg=CFG, **kwargs):
    client = FakeClient([prs_page([pr_node(number=99, **kwargs)])])
    return collect_prs(client, "wing/abci", SINCE, cfg)[0]


def test_infer_l5_auto_merged_agent_pr():
    t = infer_one(author="claude[bot]", author_type="Bot",
                  merged_by=("claude[bot]", "Bot"), commits=(CLAUDE_FOOTER,))
    assert t.level == "L5" and t.method == "inference:auto-merged-agent-pr"


def test_infer_l4_agent_pr_human_final_review():
    t = infer_one(author="claude[bot]", author_type="Bot",
                  reviews=(("APPROVED", "wing", "User"),), commits=(CLAUDE_FOOTER,))
    assert t.level == "L4" and t.method == "inference:agent-pr-final-review-only"


def test_infer_l3_agent_pr_with_checkpoints():
    t = infer_one(author="claude[bot]", author_type="Bot", threads=2,
                  reviews=(("APPROVED", "wing", "User"),), commits=(CLAUDE_FOOTER,))
    assert t.level == "L3" and t.method == "inference:agent-pr-with-checkpoints"


def test_infer_l4_all_ai_commits_with_tests():
    t = infer_one(commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  files=("src/app.py", "tests/test_app.py"))
    assert t.level == "L4" and t.method == "inference:ai-end-to-end-with-tests"


def test_infer_l3_all_ai_commits_no_tests():
    t = infer_one(commits=(CLAUDE_FOOTER,), files=("src/app.py",))
    assert t.level == "L3" and t.method == "inference:ai-authored-no-tests"


def test_infer_l3_changes_requested_means_checkpoints():
    t = infer_one(commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  reviews=(("CHANGES_REQUESTED", "bob", "User"),),
                  files=("tests/test_app.py",))
    assert t.level == "L3" and t.method == "inference:checkpoints-or-mixed-commits"


def test_infer_l2_ai_minority_human_led():
    t = infer_one(commits=(CLAUDE_FOOTER, "fix: a", "fix: b", "fix: c"))
    assert t.level == "L2" and t.method == "inference:human-led-ai-assist"


def test_infer_none_without_ai_evidence():
    t = infer_one(commits=("fix: plain human commit",))
    assert t.level is None and t.method is None


def test_trailer_beats_inference():
    t = infer_one(author="claude[bot]", author_type="Bot",
                  merged_by=("claude[bot]", "Bot"),
                  body="AI-Level: L2", commits=(CLAUDE_FOOTER,))
    assert t.level == "L2" and t.method == "trailer"


def test_inference_disabled_falls_back_to_rules():
    cfg = {**CFG, "smart_inference": False}
    client = FakeClient([prs_page([
        pr_node(number=11, commits=(CLAUDE_FOOTER,), files=("tests/test_app.py",)),
    ])])
    tasks = collect_prs(client, "wing/abci", SINCE, cfg)
    assert tasks[0].level == "L3" and tasks[0].method == "rule"


# ------------------------------------------------------- claim verification

def test_verify_l5_claim_on_human_pr_is_suspect():
    t = infer_one(body="AI-Level: L5")  # human-opened PR claiming full autonomy
    assert t.level == "L5" and t.method == "trailer"
    assert t.check == "suspect:l5-claim-on-human-pipeline"


def test_verify_l4_claim_with_review_churn_is_suspect():
    t = infer_one(labels=("ai-level/L4",), commits=(CLAUDE_FOOTER,),
                  reviews=(("CHANGES_REQUESTED", "bob", "User"),),
                  files=("tests/test_app.py",))
    assert t.level == "L4" and t.check == "suspect:human-gates-observed"


def test_verify_l4_claim_without_tests_is_suspect():
    t = infer_one(body="AI-Level: L4", commits=(CLAUDE_FOOTER,),
                  files=("src/app.py",), add=200)
    assert t.level == "L4" and t.check == "suspect:no-tests-in-diff"


def test_verify_clean_l4_claim_is_ok():
    t = infer_one(body="AI-Level: L4", commits=(CLAUDE_FOOTER,),
                  files=("src/app.py", "tests/test_app.py"))
    assert t.level == "L4" and t.check == "ok"


def test_verify_l3_claim_with_churn_is_ok():
    t = infer_one(labels=("ai-level/L3",), threads=3, commits=(CLAUDE_FOOTER,))
    assert t.level == "L3" and t.check == "ok"  # churn is consistent with L3


def test_inferred_and_commit_tasks_have_no_check():
    inferred = infer_one(commits=(CLAUDE_FOOTER,))
    assert inferred.method.startswith("inference:") and inferred.check is None
    client = FakeClient([commits_page([
        commit_node(sha="fff9999", message="feat: x\n\nAI-Level: L4"),
    ])])
    commit_task = collect_commits(client, "wing/abci", "main", SINCE, CFG, skip_pr_commits=True)[0]
    assert commit_task.level == "L4" and commit_task.check is None  # unverifiable


# ------------------------------------------------------------- SOP mode

SOP_CFG = {**CFG, "sop_paths": ["testcases/"]}


def test_sop_mode_testcase_artifact_implies_l3_without_footers():
    t = infer_one(cfg=SOP_CFG, commits=("feat: discount codes",),
                  files=("src/app.py", "testcases/feature-discount/testcases_20260612.md"))
    assert t.level == "L3" and t.method == "inference:sop-testcase-flow"


def test_sop_mode_ai_footer_without_artifact_is_l2():
    t = infer_one(cfg=SOP_CFG, commits=(CLAUDE_FOOTER,), files=("src/app.py",))
    assert t.level == "L2" and t.method == "inference:ai-without-sop-flow"


def test_sop_mode_no_evidence_falls_back_to_configured_level():
    cfg = {**SOP_CFG, "no_evidence_level": "L1"}
    t = infer_one(cfg=cfg, commits=("fix: plain human commit",), files=("src/app.py",))
    assert t.level == "L1" and t.method == "inference:no-ai-evidence-default"


def test_sop_mode_bot_pipeline_still_l5():
    t = infer_one(cfg=SOP_CFG, author="claude[bot]", author_type="Bot",
                  merged_by=("claude[bot]", "Bot"), commits=(CLAUDE_FOOTER,),
                  files=("testcases/x/log.md",))
    assert t.level == "L5"


def test_verify_l3_claim_without_sop_artifact_is_suspect():
    t = infer_one(cfg=SOP_CFG, body="AI-Level: L3",
                  commits=(CLAUDE_FOOTER,), files=("src/app.py",))
    assert t.level == "L3" and t.check == "suspect:sop-artifacts-missing"


def test_verify_l3_claim_with_sop_artifact_is_ok():
    t = infer_one(cfg=SOP_CFG, labels=("ai-level/L3",),
                  files=("testcases/f/log.md", "src/app.py"))
    assert t.level == "L3" and t.check == "ok"


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
