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
    collect_issues,
    collect_prs,
    extract_signals,
    load_config,
    normalize_level,
    rework_rounds,
)

CFG = DEFAULT_CLASSIFY
SINCE = "2026-04-01T00:00:00+00:00"


class FakeClient:
    """Returns canned GraphQL responses in call order."""

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def graphql(self, query: str, variables: dict, **kw) -> dict:
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
            threads=0, files=(), branch="feature/demo",
            created="2026-05-01T10:00:00Z", closed=None, ci=None, base="main",
            dismissed=(), pushes=()):
    """Build a fake PR node.

    reviews:   (state, login, __typename) or (state, login, __typename, submittedAt)
    dismissed: (previousReviewState, login, __typename, submittedAt) — reviews GitHub
               has rewritten to DISMISSED, which survive only on the timeline
    pushes:    committedDate per commit, positionally; commits past the end of this
               tuple fall back to a fixed early date
    """
    rows = [
        {"state": r[0],
         "author": {"login": r[1], "__typename": r[2]},
         "submittedAt": r[3] if len(r) > 3 else "2026-05-01T12:00:00Z"}
        for r in reviews
    ]
    return {
        "number": number,
        "headRefName": branch,
        "baseRefName": base,
        "title": title,
        "body": body,
        "mergedAt": merged,
        "createdAt": created,
        "closedAt": closed or merged or updated,
        "updatedAt": updated or merged,
        "additions": add,
        "deletions": 5,
        "url": f"https://github.com/wing/abci/pull/{number}",
        "author": {"login": author, "__typename": author_type},
        "mergedBy": {"login": merged_by[0], "__typename": merged_by[1]},
        "autoMergeRequest": {"enabledBy": {"login": "agent"}} if auto_merge else None,
        "reviews": {
            "nodes": [{"state": r["state"], "author": r["author"]} for r in rows],
        },
        "rejections": {"nodes": [
            {"author": r["author"], "submittedAt": r["submittedAt"]}
            for r in rows if r["state"] == "CHANGES_REQUESTED"
        ]},
        "timelineItems": {"nodes": [
            {"previousReviewState": st,
             "review": {"submittedAt": at,
                                 "author": {"login": lg, "__typename": tp}}}
            for (st, lg, tp, at) in dismissed
        ]},
        "reviewThreads": {"totalCount": threads},
        "labels": {"nodes": [{"name": l} for l in labels]},
        "commits": {"nodes": [
            {"commit": {"message": m,
                        "committedDate": pushes[i] if i < len(pushes)
                        else "2026-05-01T09:00:00Z"}}
            for i, m in enumerate(commits)
        ]},
        "lastCommit": {"nodes": [{"commit": {"statusCheckRollup": {"state": ci} if ci else None}}]},
        "files": {"nodes": [
            {"path": f, "changeType": "MODIFIED"} if isinstance(f, str)
            else {"path": f[0], "changeType": f[1]} for f in files
        ]},
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
    assert tasks[0].branch == "main"  # commits carry the scanned branch
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
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert [t.id for t in tasks] == ["10"]
    assert tasks[0].level == "L4" and tasks[0].method == "label" and tasks[0].kind == "pr"
    assert tasks[0].branch == "feature/demo"


def test_collect_prs_stops_when_page_is_stale():
    client = FakeClient([
        prs_page([pr_node(number=3, merged="2026-02-01T00:00:00Z",
                          updated="2026-02-02T00:00:00Z")], has_next=True, cursor="P1"),
        prs_page([pr_node(number=2)]),  # must never be requested
    ])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert len(client.calls) == 1  # early stop — no second page fetch


def test_collect_prs_trailer_in_body():
    client = FakeClient([prs_page([pr_node(number=7, body="details...\n\nAI-Level: 5")])])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L5" and tasks[0].method == "trailer"


def test_collect_prs_trailer_in_inner_commit():
    client = FakeClient([prs_page([
        pr_node(number=8, commits=("feat: x\n\nAI-Level: L4",)),
    ])])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L4" and tasks[0].method == "trailer"


def test_collect_prs_claude_footer_classified_by_inference():
    footer = "feat: z\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\nCo-Authored-By: Claude <noreply@anthropic.com>"
    client = FakeClient([prs_page([pr_node(number=9, commits=(footer,))])])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L3" and tasks[0].method.startswith("inference:")


def test_collect_prs_label_beats_inner_commit_signals():
    client = FakeClient([prs_page([
        pr_node(number=10, labels=("ai-level/L2",),
                commits=("feat: y\n\nAI-Level: L4\nCo-Authored-By: Claude",)),
    ])])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].level == "L2" and tasks[0].method == "label"


# ------------------------------------------------------------ inference

CLAUDE_FOOTER = (
    "feat: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
    "Co-Authored-By: Claude <noreply@anthropic.com>"
)


def infer_one(cfg=CFG, **kwargs):
    client = FakeClient([prs_page([pr_node(number=99, **kwargs)])])
    return collect_prs(client, "wing/abci", SINCE, cfg)[0][0]


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
    tasks, _ = collect_prs(client, "wing/abci", SINCE, cfg)
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
    assert t.rework == 1  # 被打回輪數傳到 task


def test_two_reviewers_on_the_same_push_is_one_round():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  merged="2026-05-10T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "amy", "User", "2026-05-02T11:00:00Z"),
                           ("APPROVED", "bob", "User")),
                  pushes=("2026-05-01T09:00:00Z",))
    assert t.rework == 1


def test_rejection_after_a_push_is_a_second_round():
    t = infer_one(labels=("ai-level/L3",),
                  commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  merged="2026-05-10T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "bob", "User", "2026-05-04T10:00:00Z")),
                  pushes=("2026-05-01T09:00:00Z", "2026-05-03T09:00:00Z"))
    assert t.rework == 2


def test_reviewed_is_false_without_any_human_review():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,))
    assert t.reviewed is False


def test_reviewed_is_true_with_an_outside_review():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.reviewed is True


def test_authors_own_comment_does_not_make_a_pr_reviewed():
    # Defect 7: this is the bypass. "wing" opens the PR and comments on it.
    t = infer_one(labels=("ai-level/L3",), author="wing", commits=(CLAUDE_FOOTER,),
                  reviews=(("COMMENTED", "wing", "User"),))
    assert t.reviewed is False


def test_rework_hours_measured_from_the_first_rejection():
    # First rejection 2026-05-02T10:00Z, merged 2026-05-04T10:00Z = 48h.
    t = infer_one(labels=("ai-level/L3",),
                  commits=(CLAUDE_FOOTER, CLAUDE_FOOTER),
                  merged="2026-05-04T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),
                           ("CHANGES_REQUESTED", "amy", "User", "2026-05-03T10:00:00Z")),
                  pushes=("2026-05-01T09:00:00Z", "2026-05-02T20:00:00Z"))
    assert t.rework_hours == 48.0


def test_no_rejection_means_no_rework_hours():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.rework == 0 and t.rework_hours is None


def test_rejection_after_merge_is_not_rework():
    # A slower reviewer's "Request changes" can land after a race auto-merge.
    # The only rejection is submitted after mergedAt, so nothing was reworked —
    # it counts as neither a rework round nor turnaround time.
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  merged="2026-05-02T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T11:00:00Z"),))
    assert t.rework == 0
    assert t.rework_hours is None


def test_rejection_exactly_at_merge_is_not_rework():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  merged="2026-05-04T10:00:00Z",
                  reviews=(("CHANGES_REQUESTED", "bob", "User", "2026-05-04T10:00:00Z"),),
                  pushes=("2026-05-01T09:00:00Z",))
    assert t.rework == 0 and t.rework_hours is None


def test_dismissed_rejection_is_still_counted():
    # GitHub rewrites the review's state to DISMISSED, so it survives only on
    # the timeline. Dismissing a rejection must not erase that it happened.
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  merged="2026-05-10T10:00:00Z",
                  dismissed=(("CHANGES_REQUESTED", "bob", "User", "2026-05-02T10:00:00Z"),),
                  pushes=("2026-05-01T09:00:00Z",))
    assert t.rework == 1


def test_dismissed_rejection_still_counts_as_changes_requested():
    # Same fact pattern as test_dismissed_rejection_is_still_counted, but
    # pinning the extract_signals()/PrSignals half of the redefinition
    # directly — infer_level and verify_claim both read changes_requested,
    # not t.rework, as their evidence of a human gate.
    node = pr_node(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                    merged="2026-05-10T10:00:00Z",
                    dismissed=(("CHANGES_REQUESTED", "bob", "User",
                                "2026-05-02T10:00:00Z"),),
                    pushes=("2026-05-01T09:00:00Z",))
    sig = extract_signals(node, CFG)
    assert sig.changes_requested >= 1


def test_dismissed_approval_is_not_counted_as_rework():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  dismissed=(("APPROVED", "bob", "User", "2026-05-02T10:00:00Z"),))
    assert t.rework == 0


def test_bot_rejection_is_not_counted():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("CHANGES_REQUESTED", "sonar[bot]", "Bot",
                            "2026-05-02T10:00:00Z"),))
    assert t.rework == 0


# ------------------------------------------------------- rework rounds

def test_rework_rounds_no_rejections_is_zero():
    assert rework_rounds([], ["2026-05-01T09:00:00Z"]) == 0


def test_rework_rounds_two_reviewers_same_push_is_one_round():
    # Amy and Bob both reject the same code — one round trip for the author.
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-02T11:00:00Z"],
        ["2026-05-01T09:00:00Z"],
    ) == 1


def test_rework_rounds_push_between_rejections_starts_a_new_round():
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-04T10:00:00Z"],
        ["2026-05-01T09:00:00Z", "2026-05-03T09:00:00Z"],
    ) == 2


def test_rework_rounds_sorts_its_input():
    # GitHub does not promise ordering; the function must not trust it.
    assert rework_rounds(
        ["2026-05-04T10:00:00Z", "2026-05-02T10:00:00Z"],
        ["2026-05-03T09:00:00Z"],
    ) == 2


def test_rework_rounds_push_before_first_rejection_does_not_add_a_round():
    assert rework_rounds(
        ["2026-05-02T10:00:00Z"],
        ["2026-05-01T09:00:00Z", "2026-05-01T10:00:00Z"],
    ) == 1


def test_rework_rounds_push_equal_to_earlier_rejection_does_not_add_round():
    # Boundary case: push timestamp exactly equals the earlier rejection.
    # The condition `prev < p <= cur` requires p to be strictly after prev,
    # so a push equal to prev does NOT count as between rejections.
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-02T11:00:00Z"],
        ["2026-05-02T10:00:00Z"],
    ) == 1


def test_rework_rounds_push_equal_to_later_rejection_adds_round():
    # Boundary case: push timestamp exactly equals the later rejection.
    # The condition `prev < p <= cur` is true when p equals cur and prev < p,
    # so a push equal to cur DOES count as between rejections.
    assert rework_rounds(
        ["2026-05-02T10:00:00Z", "2026-05-02T11:00:00Z"],
        ["2026-05-02T11:00:00Z"],
    ) == 2


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


# ------------------------------------------------- direct-to-main commits

AI_STYLE_MSG = (
    "feat: restore qa_signoff package and release sign-off workflow\n\n"
    "PR merged the spec but not its implementation. This restores the\n"
    "package onto the main line and rewires the release workflow.\n\n"
    "- add qa_signoff package with regression runner\n"
    "- wire sign-off gate into release workflow"
)


def commit_one(message, cfg=CFG):
    client = FakeClient([commits_page([commit_node(sha="abc0001", message=message)])])
    return collect_commits(client, "wing/abci", "main", SINCE, cfg, skip_pr_commits=True)[0]


@pytest.mark.parametrize("message,expected", [
    (AI_STYLE_MSG, True),                       # prefix + long body + bullets
    ("fix typo", False),                        # bare human quickie
    ("feat: add x", False),                     # prefix alone isn't enough
    ("update stuff\n\nchanged some things", False),
])
def test_looks_ai_written(message, expected):
    from collect_github import looks_ai_written
    assert looks_ai_written(message) is expected


def test_direct_commit_ai_style_message_is_l2():
    t = commit_one(AI_STYLE_MSG, cfg={**CFG, "sop_paths": ["testcases/"]})
    assert t.level == "L2" and t.method == "inference:ai-style-message"


def test_direct_commit_footer_capped_at_l2_in_sop_mode():
    t = commit_one(CLAUDE_FOOTER, cfg={**CFG, "sop_paths": ["testcases/"]})
    assert t.level == "L2" and t.method == "inference:ai-without-sop-flow"


def test_direct_commit_footer_stays_rule_l3_in_generic_mode():
    t = commit_one(CLAUDE_FOOTER)
    assert t.level == "L3" and t.method == "rule"


def test_direct_commit_human_style_falls_back_to_l1():
    t = commit_one("fix typo", cfg={**CFG, "sop_paths": ["testcases/"], "no_evidence_level": "L1"})
    assert t.level == "L1" and t.method == "inference:no-ai-evidence-default"


def test_direct_commit_trailer_still_wins():
    t = commit_one("fix typo\n\nAI-Level: L4", cfg={**CFG, "sop_paths": ["testcases/"]})
    assert t.level == "L4" and t.method == "trailer"


# ------------------------------------------- CJK 加權 + per-repo override

CJK_DETAILED_MSG = (
    "feat: 完成权限系统重构\n\n"
    "将原有的角色权限表迁移到基于 oauth 的记录方式,统一权限校验入口,"
    "同时清理旧的权限中间件并补充迁移脚本。"
)


def test_cjk_detailed_body_counts_as_ai_style():
    from collect_github import _weighted_len, looks_ai_written
    body = CJK_DETAILED_MSG.split("\n\n", 1)[1]
    assert len(body) < 80 <= _weighted_len(body)  # 冇加權會漏判
    assert looks_ai_written(CJK_DETAILED_MSG) is True


def test_cjk_one_liner_still_human_style():
    from collect_github import looks_ai_written
    assert looks_ai_written("feat: 完成知识库功能") is False


def test_per_repo_no_evidence_override():
    from collect_github import collect_repo
    client = FakeClient([commits_page([
        commit_node(sha="c000001", message="feat: 完成知识库功能"),
    ])])
    repo_cfg = {"name": "tony/abci-crm", "branch": "master",
                "no_evidence_level": "L2", "sop_paths": [], "track_issues": False}
    client.responses.extend([META_DEP_EMPTY, META_EMPTY])
    client.responses += [
        {"repository": {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": []}}},
        {"repository": {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": []}}},
        {"repository": {"milestones": {"nodes": []}}},
    ]
    tasks, _meta = collect_repo(client, repo_cfg, SINCE, "commits",
                                {**CFG, "sop_paths": ["testcases/"], "no_evidence_level": "L1"})
    assert tasks[0].level == "L2" and tasks[0].method == "inference:no-ai-evidence-default"


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


# --------------------------------------------------- DORA / meta / quality

META_DEP_EMPTY = {"repository": {"deployments": {"nodes": []}}}
META_EMPTY = {"repository": {"releases": {"nodes": []}, "refs": {"nodes": []}}}


def test_closed_unmerged_pr_counted_not_tasked():
    client = FakeClient([prs_page([
        pr_node(number=20, merged=None, closed="2026-05-03T10:00:00Z",
                updated="2026-05-03T10:00:00Z"),
        pr_node(number=21),
    ])])
    tasks, closed = collect_prs(client, "wing/abci", SINCE, CFG)
    assert [t.id for t in tasks] == ["21"]
    assert closed == ["2026-05-03"]


def test_excluded_author_closed_pr_stays_out_of_closed_unmerged():
    # A closed dependabot PR must not deflate 接受率 — README promises
    # exclude_authors means 「完全唔計呢啲 author」, merged or not.
    client = FakeClient([prs_page([
        pr_node(number=7, author="dependabot[bot]", author_type="Bot",
                merged=None, closed="2026-05-02T10:00:00Z",
                updated="2026-05-02T10:00:00Z"),
    ])])
    tasks, closed_unmerged = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert closed_unmerged == []


def test_included_author_closed_pr_is_still_counted():
    client = FakeClient([prs_page([
        pr_node(number=8, author="wing", merged=None,
                closed="2026-05-02T10:00:00Z", updated="2026-05-02T10:00:00Z"),
    ])])
    tasks, closed_unmerged = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks == []
    assert closed_unmerged == ["2026-05-02"]


def test_lead_hours_and_ci_state():
    client = FakeClient([prs_page([
        pr_node(number=22, created="2026-05-01T10:00:00Z",
                merged="2026-05-02T12:00:00Z", ci="SUCCESS"),
        pr_node(number=23, ci="FAILURE"),
    ])])
    tasks, _ = collect_prs(client, "wing/abci", SINCE, CFG)
    assert tasks[0].lead_hours == 26.0 and tasks[0].ci == "pass"
    assert tasks[1].ci == "fail"


def test_fetch_repo_meta_filters_window_and_tags():
    from collect_github import fetch_repo_meta
    client = FakeClient([
        {"repository": {"deployments": {"nodes": [{"createdAt": "2026-06-01T00:00:00Z"}]}}},
        {"repository": {
        "releases": {"nodes": [{"publishedAt": "2026-05-10T00:00:00Z"},
                               {"publishedAt": "2026-01-01T00:00:00Z"}]},
        "refs": {"nodes": [
            # annotated tag → tagger.date
            {"name": "v1.4.0", "target": {"tagger": {"date": "2026-05-20T08:00:00+08:00"}}},
            # lightweight tag → commit date
            {"name": "1.3.0", "target": {"committedDate": "2026-04-15T00:00:00Z"}},
            # 預設所有 tag 都計(改用 per-repo tag_pattern 先會過濾)
            {"name": "milestone-alpha", "target": {"committedDate": "2026-05-01T00:00:00Z"}},
            # window 之外 → 過濾
            {"name": "v1.0.0", "target": {"committedDate": "2025-12-01T00:00:00Z"}},
        ]},
    }}])
    meta = fetch_repo_meta(client, "wing/abci", SINCE)
    assert meta["releases"] == ["2026-05-10"]
    assert meta["deployments"] == ["2026-06-01"]
    assert meta["tags"] == ["2026-05-20", "2026-04-15", "2026-05-01"]


def test_fetch_repo_meta_custom_tag_pattern():
    from collect_github import fetch_repo_meta
    client = FakeClient([META_DEP_EMPTY, {"repository": {
        "releases": {"nodes": []},
        "refs": {"nodes": [
            {"name": "deploy-20260601", "target": {"committedDate": "2026-06-01T00:00:00Z"}},
            {"name": "v2.0.0", "target": {"committedDate": "2026-06-02T00:00:00Z"}},
        ]},
    }}])
    meta = fetch_repo_meta(client, "wing/abci", SINCE, tag_pattern=r"^deploy-")
    assert meta["tags"] == ["2026-06-01"]


def test_fetch_quality_file_parses_and_tolerates_failure():
    from collect_github import CollectError, fetch_quality_file

    class RawClient:
        def rest_raw(self, path):
            assert path == "/repos/wing/abci/contents/quality/metrics.json"
            return '{"coverage": 82.4, "security": {"critical": 0, "high": 1, "medium": 4}}'

    q = fetch_quality_file(RawClient(), "wing/abci", "quality/metrics.json")
    assert q["coverage"] == 82.4 and q["security"]["high"] == 1

    class FailClient:
        def rest_raw(self, path):
            raise CollectError("404")

    assert fetch_quality_file(FailClient(), "wing/abci", "x.json") is None


def test_fetch_outcomes_file_keeps_documented_metrics_and_tolerates_failure():
    from collect_github import CollectError, fetch_outcomes_file

    class RawClient:
        def rest_raw(self, path):
            assert path == "/repos/wing/abci/contents/product/outcomes.json"
            return '''{
              "updated_at": "2026-07-05",
              "adoption": [
                {"label":"Weekly active accounts","value":1840,"unit":"accounts","change":12.4,"target":2000,"ignored":"x"},
                {"label":"broken"}
              ],
              "customer": [
                {"label":"Support tickets / 1k orders","value":4.6,"unit":"tickets","change":-11.5,"direction":"down"}
              ]
            }'''

    result = fetch_outcomes_file(RawClient(), "wing/abci", "product/outcomes.json")
    assert result == {
        "updated_at": "2026-07-05",
        "adoption": [{"label": "Weekly active accounts", "value": 1840,
                      "unit": "accounts", "change": 12.4, "target": 2000}],
        "customer": [{"label": "Support tickets / 1k orders", "value": 4.6,
                      "unit": "tickets", "change": -11.5, "direction": "down"}],
    }

    class FailClient:
        def rest_raw(self, path):
            raise CollectError("404")

    assert fetch_outcomes_file(FailClient(), "wing/abci", "x.json") is None


# ---------------------------------------------------- governance red lines

def test_violation_forbidden_files_and_workflow_delete():
    t = infer_one(commits=(CLAUDE_FOOTER,),
                  files=("src/app.py", "node_modules/x/index.js",
                         (".github/workflows/ci.yml", "DELETED")),
                  reviews=(("APPROVED", "bob", "User"),))
    assert "forbidden-files" in t.violations
    assert "workflow-deleted" in t.violations


def test_violation_cross_branch_merge():
    t = infer_one(commits=(CLAUDE_FOOTER,), base="feature/other",
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.violations == ["cross-branch-merge"]


def test_violation_merged_without_review():
    t = infer_one(commits=(CLAUDE_FOOTER,))
    assert "merged-without-review" in t.violations


def test_self_commented_review_still_trips_merged_without_review():
    # Defect 7: the PR author's own COMMENTED review must not count as a
    # human review — otherwise it silently suppresses this red line.
    # infer_one defaults the PR author to "wing" (a User), so a review
    # authored by "wing" is a self-review.
    t = infer_one(commits=(CLAUDE_FOOTER,),
                  reviews=(("COMMENTED", "wing", "User"),))
    assert "merged-without-review" in t.violations


def test_pending_review_still_trips_merged_without_review():
    # An unsubmitted draft (PENDING) review is not a review of anything yet.
    t = infer_one(commits=(CLAUDE_FOOTER,),
                  reviews=(("PENDING", "bob", "User"),))
    assert "merged-without-review" in t.violations


def test_other_user_commented_review_does_not_trip_merged_without_review():
    # Contrast case: a COMMENTED review from someone other than the PR
    # author is a real human review and must suppress the red line.
    t = infer_one(commits=(CLAUDE_FOOTER,),
                  reviews=(("COMMENTED", "bob", "User"),))
    assert "merged-without-review" not in t.violations


def test_violation_oversized_pr_threshold():
    t = infer_one(commits=(CLAUDE_FOOTER,), add=900,
                  reviews=(("APPROVED", "bob", "User"),))
    assert "oversized-pr" in t.violations
    cfg = {**CFG, "max_pr_additions": 0}
    t2 = infer_one(cfg=cfg, commits=(CLAUDE_FOOTER,), add=900,
                   reviews=(("APPROVED", "bob", "User"),))
    assert "oversized-pr" not in t2.violations


def test_violation_core_paths_need_double_review():
    cfg = {**CFG, "core_paths": ["src/core/"]}
    t = infer_one(cfg=cfg, commits=(CLAUDE_FOOTER,), files=("src/core/pricing.py",),
                  reviews=(("APPROVED", "bob", "User"),))
    assert "core-without-double-review" in t.violations
    t2 = infer_one(cfg=cfg, commits=(CLAUDE_FOOTER,), files=("src/core/pricing.py",),
                   reviews=(("APPROVED", "bob", "User"), ("APPROVED", "amy", "User")))
    assert "core-without-double-review" not in t2.violations


def test_violation_direct_push_and_per_repo_off():
    t = commit_one("feat: x")
    assert t.violations == ["direct-push-main"]
    t2 = commit_one("feat: x", cfg={**CFG, "flag_direct_push": False})
    assert t2.violations == []


def test_clean_pr_has_no_violations():
    t = infer_one(commits=(CLAUDE_FOOTER,), files=("src/app.py",),
                  reviews=(("APPROVED", "bob", "User"),))
    assert t.violations == []


# ------------------------------------------------------------- planning



def test_collect_issues_parses_progress_and_milestones():
    from collect_github import collect_issues
    client = FakeClient([{"repository": {
        "openIssues": {"totalCount": 5},
        "closedIssues": {"totalCount": 15},
        "issues": {"nodes": [{
            "number": 42, "title": "feat: export PDF", "url": "https://github.com/w/r/issues/42",
            "createdAt": "2026-06-01T00:00:00Z", "updatedAt": "2026-06-20T00:00:00Z",
            "labels": {"nodes": [{"name": "P1"}, {"name": "bug"}]},
            "assignees": {"nodes": [{"login": "wing"}]},
            "milestone": {"title": "v0.2", "dueOn": "2026-07-01T00:00:00Z"},
        }]},
        "closedRecent": {"nodes": [{
            "number": 40, "title": "fix: login 500", "url": "https://github.com/w/r/issues/40",
            "closedAt": "2026-06-18T00:00:00Z",
            "labels": {"nodes": [{"name": "bug"}, {"name": "high"}]},
            "assignees": {"nodes": []},
            "milestone": None,
        }]},
        "milestones": {"nodes": [{
            "title": "v0.2", "dueOn": "2026-07-01T00:00:00Z",
            "open": {"totalCount": 3}, "closed": {"totalCount": 7},
        }]},
    }}])
    d, err = collect_issues(client, "w/r")
    assert err is None
    assert d["open_total"] == 5 and d["closed_total"] == 15
    assert d["open"][0]["labels"] == ["P1", "bug"] and d["open"][0]["due"] == "2026-07-01"
    assert d["open"][0]["assignees"] == ["wing"]
    assert d["closed_recent"][0]["number"] == 40 and d["closed_recent"][0]["closed"] == "2026-06-18"
    assert d["milestones"][0] == {"title": "v0.2", "due": "2026-07-01", "open": 3, "closed": 7}


def test_collect_issues_returns_none_on_failure():
    from collect_github import CollectError, collect_issues

    class Boom:
        def graphql(self, q, v):
            raise CollectError("403")

    data, err = collect_issues(Boom(), "w/r")
    assert data is None
    assert err == "403"


# ------------------------------------------------------------ plan file

PLAN_MD = """# HK Tax Helper — Project Plan

## Phase 1 基礎
- [x] project scaffold
- [x] 稅階 config
- [X] 免稅額 model

## Phase 2 報稅核心
- [x] 合併評稅計算
- [ ] 分開評稅比較
- [ ] IR56B parser

notes: 下面唔係 checkbox
- 普通 bullet 唔計
"""


def test_parse_plan_markdown_counts_and_sections():
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown(PLAN_MD)
    assert plan["done"] == 4 and plan["total"] == 6
    assert [s["title"] for s in plan["sections"]] == ["Phase 1 基礎", "Phase 2 報稅核心"]
    assert plan["sections"][1] == {"title": "Phase 2 報稅核心", "done": 1, "total": 3}
    assert plan["assignments"] == [] and plan["unassigned"] == 6


def test_plan_assignees_count_every_task_and_are_stripped_from_titles():
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown(
        "# Plan\n"
        "- [x] shipped auth assignee:@wing\n"
        "- [ ] build reports assignee:Tony\n"
        "- [ ] test reports assignee:wing\n"
        "- [ ] unowned work\n"
    )
    assert plan["assignments"] == [
        {"name": "wing", "tasks": 2}, {"name": "Tony", "tasks": 1},
    ]
    assert plan["unassigned"] == 1
    assert plan["open_tasks"][0]["title"] == "build reports"
    assert plan["open_tasks"][0]["assignee"] == "Tony"


def test_plan_scheduled_rows_use_github_mentions_for_work_allocation():
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown(
        "**M1 · Foundation, navigation & design system**\n"
        "Navigation architecture @Tony-Liu-1248 start:2026-01-20 done:2026-07-06\n"
        "Shared component library @pie-csi start:2026-01-20 done:2026-08-02\n"
        "Maven Pro type ramp @wing-csi start:2026-02-27 done:2026-05-18\n"
        "PNG icon sets converted to SVG @Tony-Liu-1248 start:2026-05-03\n"
    )
    assert plan["done"] == 3 and plan["total"] == 4
    assert plan["assignments"] == [
        {"name": "Tony-Liu-1248", "tasks": 2},
        {"name": "pie-csi", "tasks": 1},
        {"name": "wing-csi", "tasks": 1},
    ]
    assert plan["unassigned"] == 0
    assert plan["sections"] == [{
        "title": "M1 · Foundation, navigation & design system", "done": 3, "total": 4,
    }]
    assert plan["open_tasks"][0]["title"] == "PNG icon sets converted to SVG"
    assert plan["open_tasks"][0]["assignee"] == "Tony-Liu-1248"


def test_plan_checkbox_accepts_a_standalone_github_mention():
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("- [ ] build reports @pie-csi due:2026-08-20\n")
    assert plan["assignments"] == [{"name": "pie-csi", "tasks": 1}]
    assert plan["open_tasks"][0]["title"] == "build reports"
    assert plan["open_tasks"][0]["assignee"] == "pie-csi"


def test_plan_file_none_when_missing_or_not_a_plan():
    from collect_github import CollectError, fetch_plan_file, parse_plan_markdown
    assert parse_plan_markdown("# 冇 checkbox 嘅普通 README") is None

    class Boom:
        def rest_raw(self, path):
            raise CollectError("404")

    assert fetch_plan_file(Boom(), "w/r", "plan.md") is None

    class Ok:
        def rest_raw(self, path):
            return PLAN_MD

    plan = fetch_plan_file(Ok(), "w/r", "docs/plan.md")
    assert plan["total"] == 6 and plan["path"] == "docs/plan.md"


PLAN_MD2 = """## Phase 2 報稅核心 due:2026-07-31
- [ ] feat: IR56B parser !P1
- [ ] fix: rounding 錯數 !P0 #bug due:2026-07-18
- [x] 合併評稅計算 !P2

## Backlog
- [ ] docs: runbook
"""


def test_plan_markers_due_priority_bug_and_inheritance():
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown(PLAN_MD2)
    t1, t2, t3 = plan["open_tasks"]
    assert t1 == {"title": "feat: IR56B parser", "due": "2026-07-31",
                  "priority": "P1", "bug": False, "assignee": None,
                  "section": "Phase 2 報稅核心"}
    assert t2["due"] == "2026-07-18" and t2["priority"] == "P0" and t2["bug"] is True
    assert t2["title"] == "fix: rounding 錯數"  # 標記已清走
    assert t3 == {"title": "docs: runbook", "due": None, "priority": None,
                  "bug": False, "assignee": None, "section": "Backlog"}
    assert plan["sections"][0]["title"] == "Phase 2 報稅核心"  # heading 唔帶 due 標記


# ------------------------------- 登記冊住喺另一條 branch(registers_ref)

DEFECT_MD = "- [ ] 匯出 CSV 中文亂碼 !P1 found:2026-07-14\n"


def test_registers_ref_reads_the_register_off_that_branch():
    """plan.md / defect.md 可以住喺一條 docs branch,唔使 merge 入 default branch。
    contents API 冇 `?ref=` 就永遠讀 default branch,而 fetch_plan_file 會將個
    404 食咗變 None — 即係靜靜當「呢個 repo 冇登記冊」,同真係冇分唔到。"""
    from collect_github import fetch_plan_file

    seen: list[str] = []

    class Ok:
        def rest_raw(self, path):
            seen.append(path)
            return PLAN_MD

    plan = fetch_plan_file(Ok(), "w/r", "plan.md", ref="docs/management-dashboard-registers")
    assert seen == ["/repos/w/r/contents/plan.md?ref=docs/management-dashboard-registers"]
    assert plan["total"] == 6


def test_registers_ref_is_a_separate_field_and_stays_out_of_the_path():
    """個 path 直接餵去前端砌 blob URL,所以 query string 唔可以漏入去;
    branch 自己一個欄位,前端先砌到 blob/<ref>/<path>。"""
    from collect_github import fetch_defect_file

    class Ok:
        def rest_raw(self, path):
            return DEFECT_MD

    dfx = fetch_defect_file(Ok(), "w/r", "defect.md", ref="docs/registers")
    assert dfx["path"] == "defect.md"
    assert dfx["ref"] == "docs/registers"


def test_without_a_ref_the_call_and_the_meta_are_unchanged():
    """絕大部分 repo 唔會設 registers_ref — 佢哋條 URL 同 meta 要一模一樣。"""
    from collect_github import fetch_plan_file

    seen: list[str] = []

    class Ok:
        def rest_raw(self, path):
            seen.append(path)
            return PLAN_MD

    plan = fetch_plan_file(Ok(), "w/r", "docs/plan.md")
    assert seen == ["/repos/w/r/contents/docs/plan.md"]
    assert plan["ref"] is None


def test_collect_repo_hands_the_registers_ref_to_both_registers():
    """一個 config key 覆蓋兩份登記冊 — 分開兩個 key 只會令人設漏一個,
    然後靜靜少咗半邊數據。"""
    from collect_github import collect_repo

    class RegisterClient(FakeClient):
        def __init__(self, responses):
            super().__init__(responses)
            self.raw_paths: list[str] = []

        def rest_raw(self, path):
            self.raw_paths.append(path)
            return PLAN_MD if "plan.md" in path else DEFECT_MD

    client = RegisterClient([
        DEFAULT_BRANCH_RESP, commits_page([]), META_DEP_EMPTY, META_EMPTY,
    ])
    repo_cfg = {"name": "w/r", "plan_file": "plan.md", "defect_file": "defect.md",
                "registers_ref": "docs/management-dashboard-registers",
                "track_issues": False}
    _tasks, meta = collect_repo(client, repo_cfg, SINCE, "commits", CFG)
    assert client.raw_paths == [
        "/repos/w/r/contents/plan.md?ref=docs/management-dashboard-registers",
        "/repos/w/r/contents/defect.md?ref=docs/management-dashboard-registers",
    ]
    assert meta["plan"]["ref"] == "docs/management-dashboard-registers"
    assert meta["defects"]["ref"] == "docs/management-dashboard-registers"


def test_fetch_repo_meta_languages_and_disk():
    from collect_github import fetch_repo_meta
    client = FakeClient([META_DEP_EMPTY, {"repository": {
        "diskUsage": 2048,
        "languages": {"totalSize": 1000,
                      "edges": [{"size": 700, "node": {"name": "Java"}},
                                {"size": 300, "node": {"name": "Vue"}}]},
        "releases": {"nodes": []}, "refs": {"nodes": []},
    }}])
    meta = fetch_repo_meta(client, "w/r", SINCE)
    assert meta["disk_kb"] == 2048
    assert meta["languages"]["items"][0] == {"name": "Java", "bytes": 700}


# ------------------------------------------------------------ 多 branch

DEFAULT_BRANCH_RESP = {"repository": {"defaultBranchRef": {"name": "main"}}}


def test_multi_branch_commits_dedup_first_branch_wins():
    from collect_github import collect_repo
    client = FakeClient([
        DEFAULT_BRANCH_RESP,
        commits_page([commit_node(sha="aaa1111", message="feat: a"),
                      commit_node(sha="bbb2222", message="feat: b")]),   # main
        commits_page([commit_node(sha="bbb2222", message="feat: b"),
                      commit_node(sha="ccc3333", message="feat: c")]),   # develop
        META_DEP_EMPTY, META_EMPTY,
    ])
    repo_cfg = {"name": "w/r", "branches": ["main", "develop"], "track_issues": False}
    tasks, _meta = collect_repo(client, repo_cfg, SINCE, "commits", CFG)
    assert [t.id for t in tasks] == ["aaa1111", "bbb2222", "ccc3333"]
    assert next(t for t in tasks if t.id == "bbb2222").branch == "main"
    assert next(t for t in tasks if t.id == "ccc3333").branch == "develop"


def test_cross_branch_ok_when_base_is_tracked():
    client = FakeClient([prs_page([
        pr_node(number=30, base="develop", commits=(CLAUDE_FOOTER,),
                reviews=(("APPROVED", "bob", "User"),)),
        pr_node(number=31, base="feature/other", commits=(CLAUDE_FOOTER,),
                reviews=(("APPROVED", "bob", "User"),)),
    ])])
    tasks, _ = collect_prs(client, "w/r", SINCE, CFG, allowed_branches=("main", "develop"))
    by = {t.id: t for t in tasks}
    assert "cross-branch-merge" not in by["30"].violations
    assert "cross-branch-merge" in by["31"].violations


def test_per_repo_token_env_missing_fails_loud(monkeypatch, tmp_path, capsys):
    """token_env 指定嘅 env 唔存在 → 對應 repo 即刻報錯(唔會靜靜 fallback 用預設 token);
    唯一 repo 失敗 → main 返 1。全程冇網絡接觸(token 檢查喺任何 API call 之前)。"""
    import collect_github as cg
    monkeypatch.setenv("GH_METRICS_TOKEN", "default-token")
    monkeypatch.delenv("GH_TOKEN_CRM", raising=False)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[[repos]]\nname = "w/r"\ntoken_env = "GH_TOKEN_CRM"\n', encoding="utf-8")
    rc = cg.main(["--config", str(cfg_file), "--out", str(tmp_path / "m.json")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "GH_TOKEN_CRM" in err and "every repo failed" in err


def test_graphql_partial_data_tolerance():
    from collect_github import CollectError, _graphql_data
    import pytest as _pt
    body = {"data": {"repository": {"refs": {"nodes": []}}},
            "errors": [{"message": "Resource not accessible: deployments"}]}
    # allow_partial → 攞得返 data
    assert _graphql_data(body, allow_partial=True) == body["data"]
    # strict → 照舊 raise
    with _pt.raises(CollectError):
        _graphql_data(body, allow_partial=False)
    # 有 errors 冇 data → 點都 raise
    with _pt.raises(CollectError):
        _graphql_data({"data": None, "errors": [{"message": "bad"}]}, allow_partial=True)


def test_meta_survives_deployments_permission_error():
    """Deployments 欄位無權限(fine-grained token)— 獨立失敗,唔累 tags / languages。"""
    class MixedClient:
        def __init__(self):
            self.calls = 0
        def graphql(self, q, v, **kw):
            self.calls += 1
            if "deployments" in q:
                raise CollectError("Resource not accessible by personal access token")
            return {"repository": {
                "diskUsage": 512,
                "languages": {"totalSize": 100, "edges": [{"size": 100, "node": {"name": "TypeScript"}}]},
                "releases": {"nodes": []},
                "refs": {"nodes": [{"name": "#app1.2-#2.04",
                                    "target": {"committedDate": "2026-06-20T00:00:00Z"}}]},
            }}
    from collect_github import fetch_repo_meta
    meta = fetch_repo_meta(MixedClient(), "benegg/BoostBank", SINCE)
    assert meta["deployments"] == []
    assert meta["tags"] == ["2026-06-20"]
    assert meta["languages"]["items"][0]["name"] == "TypeScript"


class RaisingClient:
    """Raises CollectError on every GraphQL call (simulates a token without Issues:Read)."""

    def __init__(self, message: str = "GraphQL error: Resource not accessible"):
        self.message = message

    def graphql(self, query: str, variables: dict, **kw) -> dict:
        raise CollectError(self.message)


def test_collect_issues_reports_permission_failure():
    data, err = collect_issues(RaisingClient(), "owner/repo")
    assert data is None
    assert err is not None
    assert "not accessible" in err


def test_collect_issues_returns_no_error_on_success():
    body = {
        "repository": {
            "openIssues": {"totalCount": 2},
            "closedIssues": {"totalCount": 1},
            "issues": {"nodes": []},
            "closedRecent": {"nodes": []},
            "milestones": {"nodes": []},
        }
    }
    data, err = collect_issues(FakeClient([body]), "owner/repo")
    assert err is None
    assert data["open_total"] == 2
    assert data["closed_total"] == 1


# ---------------------------------------------------------------- people

def test_parse_people_absent_returns_empty():
    from collect_github import parse_people
    assert parse_people({}) == {}


def test_parse_people_maps_canonical_to_identities():
    from collect_github import parse_people
    got = parse_people({"people": {"Wing": ["wing-csi", "wing2036"]}})
    assert got == {"Wing": ["wing-csi", "wing2036"]}


def test_parse_people_rejects_identity_under_two_people():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="wing2036"):
        parse_people({"people": {"Wing": ["wing-csi", "wing2036"],
                                 "Shane": ["wing2036"]}})


def test_parse_people_rejects_empty_identity_list():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": []}})


def test_parse_people_rejects_non_string_identity():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": ["wing-csi", 7]}})


def test_parse_people_rejects_non_list_value():
    from collect_github import parse_people
    with pytest.raises(CollectError, match="Wing"):
        parse_people({"people": {"Wing": "wing-csi"}})


def test_load_config_carries_people(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[[repos]]\nname = "wing/abci"\n'
        '[people]\nWing = ["wing-csi", "wing2036"]\n'
    )
    cfg = load_config(cfg_file)
    assert cfg["people"] == {"Wing": ["wing-csi", "wing2036"]}


def test_load_config_without_people_is_empty(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[[repos]]\nname = "wing/abci"\n')
    assert load_config(cfg_file)["people"] == {}


# ---------------------------------------------------------------- owner

def test_resolve_owner_undeclared_is_none():
    from collect_github import resolve_owner
    assert resolve_owner({"name": "wing/abci"}, {}) is None


def test_resolve_owner_passes_through_canonical_name():
    from collect_github import resolve_owner
    people = {"Wing": ["wing-csi", "wing2036"]}
    assert resolve_owner({"name": "wing/abci", "owner": "Wing"}, people) == "Wing"


def test_resolve_owner_maps_identity_to_canonical():
    from collect_github import resolve_owner
    people = {"Wing": ["wing-csi", "wing2036"]}
    assert resolve_owner({"name": "wing/abci", "owner": "wing2036"}, people) == "Wing"


def test_resolve_owner_unknown_name_passes_through():
    """An owner who never commits is legitimate (e.g. a manager)."""
    from collect_github import resolve_owner
    assert resolve_owner({"name": "wing/abci", "owner": "Alice"}, {}) == "Alice"


def test_build_output_emits_people_and_owner():
    from collect_github import build_output
    cfg = {
        "window_days": 90, "mode": "auto",
        "repos": [{"name": "wing/abci", "owner": "wing2036"},
                  {"name": "wing/other"}],
        "people": {"Wing": ["wing-csi", "wing2036"]},
    }
    repo_meta = {"wing/abci": {}, "wing/other": {}}
    out = build_output(cfg, [], repo_meta, [], "2026-07-28T05:00:00+00:00")
    assert out["schema_version"] == 2
    assert out["people"] == {"Wing": ["wing-csi", "wing2036"]}
    assert out["repo_meta"]["wing/abci"]["owner"] == "Wing"
    assert "owner" not in out["repo_meta"]["wing/other"]


def test_build_output_omits_people_key_when_unconfigured():
    from collect_github import build_output
    cfg = {"window_days": 90, "mode": "auto",
           "repos": [{"name": "wing/abci"}], "people": {}}
    out = build_output(cfg, [], {"wing/abci": {}}, [], "2026-07-28T05:00:00+00:00")
    assert out["people"] == {}
    assert out["repos"] == ["wing/abci"]


def test_build_output_warns_on_unknown_owner(capsys):
    from collect_github import build_output
    cfg = {"window_days": 90, "mode": "auto",
           "repos": [{"name": "wing/abci", "owner": "Wng"}],
           "people": {"Wing": ["wing-csi"]}}
    build_output(cfg, [], {"wing/abci": {}}, [], "2026-07-28T05:00:00+00:00")
    assert "Wng" in capsys.readouterr().err


def test_build_output_warns_once_per_unknown_owner(capsys):
    """A non-committing owner of many repos is one fact, not N nightly warnings."""
    from collect_github import build_output
    repos = [{"name": f"acme/r{i}", "owner": "Lam"} for i in range(9)]
    cfg = {"window_days": 90, "mode": "auto", "repos": repos, "people": {}}
    repo_meta = {r["name"]: {} for r in repos}
    build_output(cfg, [], repo_meta, [], "2026-07-28T05:00:00+00:00")
    err = capsys.readouterr().err
    assert err.count("Lam") == 1
    assert "9 repos" in err            # still says how widespread it is
    # every repo still gets the owner stamped, warning or not
    assert all(m["owner"] == "Lam" for m in repo_meta.values())


PLAN_DUE_MD = """# Remediation plan

- [x] P-01 早就做完 #bug !P1 due:2026-07-10
- [ ] P-02 仲未做 #bug !P1 due:2026-08-01
- [x] P-03 做完但係最遲 #bug !P2 due:2026-09-18
"""

PLAN_HEADING_DUE_MD = """# Phase 2 due:2026-12-31

- [ ] 一件事 due:2026-08-01
- [ ] 另一件事 due:2026-08-15
"""

PLAN_HEADING_DUE_EARLIER_MD = """# Phase 2 due:2026-08-01

- [ ] 一件事 due:2026-09-01
- [ ] 另一件事 due:2026-08-15
"""


def test_due_max_counts_ticked_tasks():
    """打咗勾嗰個仲係最遲 due — 唔數佢,個死線會喺你 burn 緊嘅時候向前跳。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_DUE_MD)["due_max"] == "2026-09-18"


def test_due_max_prefers_a_heading_over_task_dates():
    """Heading 上面嘅 due: 會攞嚟做 due_max —— 呢個 fixture 入面嘅 heading due
    啱啱好本身就係最大,precedence 嘅真正證明喺下面嗰個 earlier-heading test。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_HEADING_DUE_MD)["due_max"] == "2026-12-31"


def test_due_max_heading_wins_even_when_earlier_than_task_dates():
    """就算 heading 嘅 due: 比最遲嗰個 task due 仲早,都係 heading 嗰個算數 ——
    明文宣告嘅死線贏過推斷出嚟嘅最遲 task,唔係淨係『啱啱好個大數』咁簡單。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_HEADING_DUE_EARLIER_MD)["due_max"] == "2026-08-01"


def test_due_max_is_none_when_the_plan_has_no_dates():
    """冇 due: 就冇理想線 — 唔可以靜靜哋作一個出嚟。"""
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n- [x] 另一件事\n")
    assert plan["due_max"] is None


PLAN_BAD_DUE_MD = """# Remediation plan

- [ ] P-01 打錯咗個月份 due:2026-13-01
- [ ] P-02 打錯咗嗰日 due:2026-08-32
- [ ] P-03 二月三十號 due:2026-02-30
- [ ] P-04 正常嘅 due:2026-09-18
"""


def test_due_max_ignores_dates_that_do_not_exist_on_the_calendar():
    """`PLAN_DUE_RE` 淨係夾個 shape,而 `due_max` 係字串 `max()` —— 所以
    `2026-13-01` > `2026-09-18`,一個打字錯誤就贏晒同年所有真日期做咗個
    項目死線。前端跟住 parse 出 NaN,張卡剩返個標題同一格白。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_BAD_DUE_MD)["due_max"] == "2026-09-18"


def test_a_plan_whose_only_due_is_invalid_has_no_due_at_all():
    """淨低一個爛日期 = 冇死線,唔係一個爛死線。"""
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("# 計劃\n\n- [ ] 一件事 due:2026-08-32\n")
    assert plan["due_max"] is None


def test_an_invalid_heading_due_falls_back_to_the_task_dates():
    """Heading 級 due: 贏 task 級,但佢要係一個真日期先算宣告到嘢 ——
    打錯咗就等於冇寫,唔可以連 task 嗰邊都一齊拉冇埋。"""
    from collect_github import parse_plan_markdown
    md = "# Phase 2 due:2026-13-01\n\n- [ ] 一件事 due:2026-08-15\n"
    assert parse_plan_markdown(md)["due_max"] == "2026-08-15"


def test_an_invalid_due_is_reported_not_dropped_in_silence(capsys):
    """靜靜哋掉走一個日期,同靜靜哋收咗佢一樣係呃人 —— 個 plan 檔喺人手
    改嘅目標 repo 度,呢度唔出聲就冇人知要改。"""
    from collect_github import parse_plan_markdown
    parse_plan_markdown(PLAN_BAD_DUE_MD, "acme/alpha plan.md")
    err = capsys.readouterr().err
    assert "acme/alpha plan.md" in err
    assert "2026-13-01" in err
    assert err.isascii(), "呢啲字會出去 Windows console,非 ASCII 會變亂碼"


def test_the_history_replay_does_not_repeat_the_warning(capsys):
    """同一行爛日期會出現喺 150 個舊 blob 入面。逐個嗌一次,真正要改嗰個
    檔嘅提示就會浸死喺自己嘅回音入面 —— 冇 source 就唔嗌。"""
    from collect_github import parse_plan_markdown
    parse_plan_markdown(PLAN_BAD_DUE_MD)
    assert capsys.readouterr().err == ""


def test_fetch_plan_file_names_the_repo_in_the_warning(capsys):
    """個 parser 自己唔知係邊個 repo;唔喺 call site 帶落去,個 warning 就
    講唔出要去邊度改。"""
    from collect_github import fetch_plan_file

    class BadDueClient:
        def rest_raw(self, path: str) -> str:
            return PLAN_BAD_DUE_MD

    plan = fetch_plan_file(BadDueClient(), "acme/alpha", "docs/plan.md")
    assert plan["due_max"] == "2026-09-18"
    err = capsys.readouterr().err
    assert "acme/alpha" in err and "docs/plan.md" in err


def test_due_max_sees_tasks_beyond_the_open_task_cap():
    """open_tasks 封頂 50,但 due_max 要掃晒成個檔 — 第 51 個 task
    嘅日期一樣係項目死線嘅一部分。"""
    from collect_github import parse_plan_markdown
    body = "".join(f"- [ ] task {i} due:2026-08-{i:02d}\n" for i in range(1, 29))
    body += "".join(f"- [ ] extra {i}\n" for i in range(40))
    body += "- [ ] 最後一個 due:2026-11-30\n"
    assert parse_plan_markdown("# 計劃\n\n" + body)["due_max"] == "2026-11-30"


# ------------------------------------------------------------ plan start:

PLAN_START_MD = """# Issue board start:2026-06-16 due:2026-09-18

- [x] 做咗嘅嘢
- [ ] 未做嘅嘢
"""


def test_a_heading_start_becomes_start_min():
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_START_MD)["start_min"] == "2026-06-16"


def test_a_plan_without_start_has_none():
    """冇宣告唔係一個錯 —— 前端會跌落下一層,唔使喺呢度作一個日期出嚟。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n")["start_min"] is None


def test_the_earliest_heading_start_wins():
    """`due:` 取 max、`start:` 取 min —— 兩個一齊圍出最闊嘅宣告窗口。"""
    from collect_github import parse_plan_markdown
    md = ("# 第一期 start:2026-06-16\n\n- [ ] 一件事\n\n"
          "# 第二期 start:2026-07-01\n\n- [ ] 另一件事\n")
    assert parse_plan_markdown(md)["start_min"] == "2026-06-16"


def test_a_task_level_start_is_not_a_project_start():
    """一個 task 幾時開始唔係項目起點。`due:` 收 task 級係因為要砌 marker,
    起點冇呢個需要 —— 收咗就會有人喺一行 checkbox 度改到成條軸。"""
    from collect_github import parse_plan_markdown
    md = "# 計劃\n\n- [ ] 一件事 start:2026-06-16\n"
    assert parse_plan_markdown(md)["start_min"] is None


def test_a_start_that_is_not_a_calendar_date_is_dropped():
    """同 due: 一樣,個 regex 淨係夾 shape。`2026-02-30` 過得 regex,但
    JS 會靜靜哋當佢係 3 月 2 日,喺條軸上面永遠 indexOf 唔到。"""
    from collect_github import parse_plan_markdown
    md = "# 計劃 start:2026-02-30\n\n- [ ] 一件事\n"
    assert parse_plan_markdown(md)["start_min"] is None


def test_a_dropped_start_warns_under_its_own_marker_name(capsys):
    """兩個 marker 唔可以共用一句講 due_max 嘅說話 —— 睇嘅人要知去改邊個字。"""
    from collect_github import parse_plan_markdown
    parse_plan_markdown("# 計劃 start:2026-02-30\n\n- [ ] 一件事\n",
                        "acme/alpha plan.md")
    err = capsys.readouterr().err
    assert "acme/alpha plan.md" in err
    assert "start:2026-02-30" in err
    assert "deadline" not in err, "呢句唔係講 due_max"
    assert err.isascii(), "呢啲字會出去 Windows console,非 ASCII 會變亂碼"


def test_start_is_stripped_from_the_section_title():
    """唔 strip 嘅話個 section title 會帶住 `start:2026-06-16` 出街。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_START_MD)["sections"][0]["title"] == "Issue board"


def test_the_due_side_still_behaves_after_the_rename():
    """`_calendar_dues` → `_calendar_dates` 係一個純改名 —— due 嗰邊
    一個字都唔應該變。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_BAD_DUE_MD)["due_max"] == "2026-09-18"


# ------------------------------------------------------------ plan history


def test_collect_repo_folds_plan_history_into_the_plan_block():
    from collect_github import DEFAULT_BRANCH_QUERY, PRS_QUERY, collect_repo

    class PlanClient:
        def graphql(self, query, variables, **kw):
            # collect_repo 行到 plan_file 之前重使 branch resolution 同 PR
            # 分頁 —— 呢兩條 query 要返真嘅形狀,其餘就用 {"repository": {}}
            # 頂住(fetch_repo_meta 對缺欄位本身就寬容)。
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            assert "/commits?" in path and "path=plan.md" in path
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_json_links(self, path):
            return [], ""   # 呢個 test 唔關 repo 開檔日事

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事 due:2026-09-18\n- [x] 另一件事\n"

    _, meta = collect_repo(PlanClient(), {"name": "acme/alpha", "plan_file": "plan.md",
                                          "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["history"] == [{"date": "2026-07-28", "done": 1, "total": 2}]
    assert meta["plan"]["history_truncated"] is False
    assert meta["plan"]["due_max"] == "2026-09-18"
    assert "history_error" not in meta["plan"]


def test_collect_repo_omits_history_when_the_commits_call_fails():
    """缺席 ≠ 空。前端要講得出「攞唔到歷史」,而唔係畫一個空圖。"""
    from collect_github import CollectError, DEFAULT_BRANCH_QUERY, PRS_QUERY, collect_repo

    class NoHistoryClient:
        def graphql(self, query, variables, **kw):
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            raise CollectError("HTTP 403")

        def rest_json_links(self, path):
            return [], ""   # 呢個 test 唔關 repo 開檔日事

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事\n"

    _, meta = collect_repo(NoHistoryClient(), {"name": "acme/alpha", "plan_file": "plan.md",
                                               "track_issues": False},
                           SINCE, "pr", CFG)
    assert "history" not in meta["plan"]
    assert "history_truncated" not in meta["plan"]
    assert meta["plan"]["history_error"]


def test_collect_repo_records_the_repo_first_commit():
    """條軸嘅 C 層後備。冇佢嘅話,一個開檔咗半年、上個月先開 plan.md
    嘅項目,條軸會由上個月起計。"""
    from collect_github import DEFAULT_BRANCH_QUERY, PRS_QUERY, collect_repo

    class FirstCommitClient:
        def graphql(self, query, variables, **kw):
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_json_links(self, path):
            if path.endswith("page=1"):
                return ([{"sha": "new",
                          "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}],
                        '<https://api.github.com/repositories/1/commits'
                        '?per_page=1&page=9>; rel="last"')
            return ([{"sha": "old",
                      "commit": {"committer": {"date": "2026-05-03T08:00:00Z"}}}], "")

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事 due:2026-09-18\n"

    _, meta = collect_repo(FirstCommitClient(),
                           {"name": "acme/alpha", "plan_file": "plan.md",
                            "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["repo_first_commit"] == "2026-05-03"


def test_an_unreadable_first_commit_leaves_the_key_null_not_missing():
    """None 同「攞唔到」喺前端係同一件事(跌落下一層),但 key 要在,先
    分得出「呢份數據行過呢段代碼」同「呢份數據舊過呢個 feature」。"""
    from collect_github import (CollectError, DEFAULT_BRANCH_QUERY, PRS_QUERY,
                                collect_repo)

    class NoFirstCommitClient:
        def graphql(self, query, variables, **kw):
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_json_links(self, path):
            raise CollectError("HTTP 409")

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事\n"

    _, meta = collect_repo(NoFirstCommitClient(),
                           {"name": "acme/alpha", "plan_file": "plan.md",
                            "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["repo_first_commit"] is None


def test_a_plan_without_history_support_leaves_both_keys_off():
    """舊 metrics.json 兩個 key 都冇 — 前端靠呢點分得出「讀唔到」同
    「呢份數據未有呢個 feature」,而兩者要做嘅嘢啱啱相反。"""
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n")
    assert "history" not in plan and "history_error" not in plan
