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
            threads=0, files=(), branch="feature/demo",
            created="2026-05-01T10:00:00Z", closed=None, ci=None):
    return {
        "number": number,
        "headRefName": branch,
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
        "reviews": {"nodes": [
            {"state": st, "author": {"login": lg, "__typename": tp}}
            for (st, lg, tp) in reviews
        ]},
        "reviewThreads": {"totalCount": threads},
        "labels": {"nodes": [{"name": l} for l in labels]},
        "commits": {"nodes": [{"commit": {"message": m}} for m in commits]},
        "lastCommit": {"nodes": [{"commit": {"statusCheckRollup": {"state": ci} if ci else None}}]},
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
    assert t.rework == 1  # 被打回次數傳到 task


def test_pr_rework_counts_multiple_changes_requested():
    t = infer_one(labels=("ai-level/L3",), commits=(CLAUDE_FOOTER,),
                  reviews=(("CHANGES_REQUESTED", "bob", "User"),
                           ("CHANGES_REQUESTED", "amy", "User"),
                           ("APPROVED", "bob", "User")))
    assert t.rework == 2


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
                "no_evidence_level": "L2", "sop_paths": []}
    client.responses.append(META_EMPTY)
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

META_EMPTY = {"repository": {"releases": {"nodes": []}, "deployments": {"nodes": []}, "refs": {"nodes": []}}}


def test_closed_unmerged_pr_counted_not_tasked():
    client = FakeClient([prs_page([
        pr_node(number=20, merged=None, closed="2026-05-03T10:00:00Z",
                updated="2026-05-03T10:00:00Z"),
        pr_node(number=21),
    ])])
    tasks, closed = collect_prs(client, "wing/abci", SINCE, CFG)
    assert [t.id for t in tasks] == ["21"]
    assert closed == ["2026-05-03"]


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
    client = FakeClient([{"repository": {
        "releases": {"nodes": [{"publishedAt": "2026-05-10T00:00:00Z"},
                               {"publishedAt": "2026-01-01T00:00:00Z"}]},
        "deployments": {"nodes": [{"createdAt": "2026-06-01T00:00:00Z"}]},
        "refs": {"nodes": [
            # annotated tag → tagger.date
            {"name": "v1.4.0", "target": {"tagger": {"date": "2026-05-20T08:00:00+08:00"}}},
            # lightweight tag → commit date
            {"name": "1.3.0", "target": {"committedDate": "2026-04-15T00:00:00Z"}},
            # 唔似版本號 → 過濾
            {"name": "milestone-alpha", "target": {"committedDate": "2026-05-01T00:00:00Z"}},
            # window 之外 → 過濾
            {"name": "v1.0.0", "target": {"committedDate": "2025-12-01T00:00:00Z"}},
        ]},
    }}])
    meta = fetch_repo_meta(client, "wing/abci", SINCE)
    assert meta["releases"] == ["2026-05-10"]
    assert meta["deployments"] == ["2026-06-01"]
    assert meta["tags"] == ["2026-05-20", "2026-04-15"]


def test_fetch_repo_meta_custom_tag_pattern():
    from collect_github import fetch_repo_meta
    client = FakeClient([{"repository": {
        "releases": {"nodes": []}, "deployments": {"nodes": []},
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
