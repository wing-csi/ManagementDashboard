#!/usr/bin/env python3
"""Collect commits and merged PRs from GitHub repos and classify AI-Level.

Reads a TOML config listing repos, pulls history via the GitHub GraphQL API,
classifies each task's autonomy level (L1–L5), and writes a flat task list
that docs/index.html aggregates client-side.

Classification priority (first match wins):
    1. PR label            e.g. ai-level/L3
    2. Trailer in message  e.g. "AI-Level: L3" in commit message, PR body,
                           or any commit message inside the PR
    3. Author mapping      config [classify.author_levels]
    4. Smart inference     (PRs only, config smart_inference) — infer L2–L5
                           from PR behaviour: agent-authored? review rounds?
                           AI/human commit mix? tests in diff? auto-merge?
    5. Heuristic rules     config [[classify.rules]] substring match

Task unit depends on `mode`:
    auto     merged PRs + commits with no associated PR (no double counting)
    pr       merged PRs only
    commits  all non-merge commits on the branch

Stdlib only (Python >= 3.11 for tomllib). Auth via GH_METRICS_TOKEN or
GITHUB_TOKEN env var; the token needs Contents:Read + Pull requests:Read
on every configured repo.

Usage:
    python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"
LEVEL_RE = re.compile(r"^L?([1-5])$", re.IGNORECASE)
MAX_PAGES = 20

DEFAULT_CLASSIFY = {
    "label_prefix": "ai-level/",
    "trailer_key": "AI-Level",
    "exclude_authors": ["dependabot[bot]", "renovate[bot]", "github-actions[bot]"],
    "author_levels": {},
    "agent_authors": [],  # logins treated as coding agents for inference
    "smart_inference": True,  # infer level from PR review/merge behaviour
    "sop_paths": [],  # diff touching these prefixes = SOP flow fingerprint → L3
    "no_evidence_level": "",  # level to assign with zero AI evidence ("" = unclassified)
    # ---- governance red lines (規範四 / 4.3 高風險檔) ----
    "flag_direct_push": True,  # direct commit to the scanned branch = violation
    "flag_unreviewed_merge": True,  # merged PR with zero human reviews
    "max_pr_additions": 800,  # 「分階段提 PR」proxy;0 = off
    "core_paths": [],  # 高風險路徑:掂到但 approvals < 2 → violation
    "track_issues": True,  # 收集 Issues / Milestones 做項目進度
    "rules": [
        {"contains": "generated with [claude code]", "level": "L3"},
        {"contains": "co-authored-by: claude", "level": "L3"},
    ],
}

DEFAULT_BRANCH_QUERY = """
query($owner:String!,$name:String!){
  repository(owner:$owner,name:$name){ defaultBranchRef{ name } }
}"""

COMMITS_QUERY = """
query($owner:String!,$name:String!,$expr:String!,$since:GitTimestamp!,$cursor:String){
  repository(owner:$owner,name:$name){
    object(expression:$expr){
      ... on Commit {
        history(since:$since, first:100, after:$cursor){
          pageInfo{ hasNextPage endCursor }
          nodes{
            abbreviatedOid committedDate message additions deletions url
            parents{ totalCount }
            author{ name user{ login } }
            associatedPullRequests(first:1){ totalCount }
          }
        }
      }
    }
  }
}"""

PRS_QUERY = """
query($owner:String!,$name:String!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequests(states:[MERGED, CLOSED], first:50, orderBy:{field:UPDATED_AT, direction:DESC}, after:$cursor){
      pageInfo{ hasNextPage endCursor }
      nodes{
        number title body mergedAt createdAt closedAt updatedAt additions deletions url headRefName baseRefName
        author{ login __typename }
        mergedBy{ login __typename }
        autoMergeRequest{ enabledBy{ login } }
        reviews(first:50){ nodes{ state author{ login __typename } } }
        reviewThreads(first:1){ totalCount }
        labels(first:20){ nodes{ name } }
        commits(first:50){ nodes{ commit{ message } } }
        lastCommit: commits(last:1){ nodes{ commit{ statusCheckRollup{ state } } } }
        files(first:100){ nodes{ path changeType } }
      }
    }
  }
}"""

REPO_META_QUERY = """
query($owner:String!,$name:String!){
  repository(owner:$owner,name:$name){
    releases(first:50, orderBy:{field:CREATED_AT, direction:DESC}){ nodes{ publishedAt } }
    deployments(first:50, orderBy:{field:CREATED_AT, direction:DESC}){ nodes{ createdAt } }
    refs(refPrefix:"refs/tags/", first:100, orderBy:{field:TAG_COMMIT_DATE, direction:DESC}){
      nodes{
        name
        target{ ... on Commit { committedDate } ... on Tag { tagger { date } } }
      }
    }
  }
}"""

ISSUES_QUERY = """
query($owner:String!,$name:String!){
  repository(owner:$owner,name:$name){
    openIssues: issues(states:[OPEN]){ totalCount }
    closedIssues: issues(states:[CLOSED]){ totalCount }
    issues(first:100, states:[OPEN], orderBy:{field:UPDATED_AT, direction:DESC}){
      nodes{
        number title url createdAt updatedAt
        labels(first:10){ nodes{ name } }
        milestone{ title dueOn }
      }
    }
    milestones(first:20, states:[OPEN], orderBy:{field:DUE_DATE, direction:ASC}){
      nodes{
        title dueOn
        open: issues(states:[OPEN]){ totalCount }
        closed: issues(states:[CLOSED]){ totalCount }
      }
    }
  }
}"""

TEST_PATH_RE = re.compile(
    r"(^|/)tests?/|(^|/)test_|_test\.|\.test\.|\.spec\.|Test\.java$|Tests\.java$|Spec\."
)

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|style|perf|ci|build|revert)(\(.+\))?!?:", re.IGNORECASE
)
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def _weighted_len(text: str) -> int:
    """Length with CJK characters counted double — one CJK char carries roughly
    the information of 2-3 Latin characters, so Latin-calibrated thresholds
    would systematically under-score Chinese/Japanese/Korean messages."""
    return len(text) + len(CJK_RE.findall(text))


def looks_ai_written(message: str) -> bool:
    """Stylometric guess: does this commit message read like agent output?

    Weakest evidence tier — structural features only (conventional prefix,
    detailed body, descriptive subject, bullet structure). Score >= 2 of 4.
    A one-line "fix typo" scores 0; typical Claude Code messages score 3-4.
    """
    lines = message.strip().splitlines()
    subject = lines[0] if lines else ""
    body = "\n".join(lines[1:]).strip()
    score = 0
    if CONVENTIONAL_RE.match(subject):
        score += 1
    if _weighted_len(body) >= 80:
        score += 1
    if _weighted_len(subject) >= 40:
        score += 1
    if re.search(r"^\s*[-*] ", body, re.MULTILINE):
        score += 1
    return score >= 2


class CollectError(Exception):
    """Raised when collection for a repo cannot proceed."""


@dataclass
class Task:
    repo: str
    kind: str  # "pr" | "commit"
    id: str  # PR number (as str) or abbreviated sha
    url: str
    date: str  # YYYY-MM-DD
    title: str
    level: str | None
    method: str | None  # "label" | "trailer" | "author" | "inference:*" | "rule" | None
    additions: int
    deletions: int
    author: str
    check: str | None = None  # claim verification: "ok" | "suspect:*" | None (unverifiable)
    branch: str = ""  # PR head branch, or the scanned branch for commits
    rework: int = 0  # human CHANGES_REQUESTED reviews on the PR (被打回次數)
    violations: list[str] = field(default_factory=list)  # governance red-line hits
    lead_hours: float | None = None  # PR createdAt → mergedAt (lead time to merge)
    ci: str | None = None  # last-commit check rollup: "pass" | "fail" | None


class GitHubClient:
    """Minimal GraphQL client over urllib."""

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ManagementDashboard",
        }

    def graphql(self, query: str, variables: dict) -> dict:
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise CollectError(f"HTTP {e.code} from GitHub API: {e.read().decode()[:200]}") from e
        except urllib.error.URLError as e:
            raise CollectError(f"network error reaching GitHub API: {e.reason}") from e
        if body.get("errors"):
            raise CollectError(f"GraphQL error: {body['errors'][0].get('message', body['errors'])}")
        return body["data"]

    def rest_raw(self, path: str) -> str:
        """GET a REST path returning the raw payload (e.g. file contents)."""
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={**self._headers, "Accept": "application/vnd.github.raw+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode()
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise CollectError(f"REST fetch {path} failed: {e}") from e


def normalize_level(raw: str) -> str | None:
    match = LEVEL_RE.match(raw.strip())
    return f"L{match.group(1)}" if match else None


def classify_explicit(
    cfg: dict, *, labels: tuple[str, ...] = (), text: str = "", author: str = ""
) -> tuple[str | None, str | None]:
    """Explicit signals only: label → trailer → author mapping."""
    prefix = cfg["label_prefix"].lower()
    for label in labels:
        if label.lower().startswith(prefix):
            level = normalize_level(label[len(prefix):])
            if level:
                return level, "label"

    trailer_re = re.compile(
        rf"^{re.escape(cfg['trailer_key'])}:\s*(L?[1-5])\s*$", re.IGNORECASE | re.MULTILINE
    )
    match = trailer_re.search(text)
    if match:
        return normalize_level(match.group(1)), "trailer"

    mapped = cfg["author_levels"].get(author)
    if mapped and normalize_level(mapped):
        return normalize_level(mapped), "author"
    return None, None


def classify_rules(cfg: dict, text: str) -> tuple[str | None, str | None]:
    """Fallback substring heuristics from config."""
    lowered = text.lower()
    for rule in cfg["rules"]:
        if rule["contains"].lower() in lowered:
            level = normalize_level(rule["level"])
            if level:
                return level, "rule"
    return None, None


def classify(
    cfg: dict, *, labels: tuple[str, ...] = (), text: str = "", author: str = ""
) -> tuple[str | None, str | None]:
    """Full ladder without behavioural inference (used for standalone commits)."""
    level, method = classify_explicit(cfg, labels=labels, text=text, author=author)
    if level:
        return level, method
    return classify_rules(cfg, text)


def classify_commit(cfg: dict, message: str, author: str) -> tuple[str | None, str | None]:
    """Ladder for a direct-to-main commit (no PR, so no behavioural signals).

    trailer/author → footer rules (capped at L2 in SOP mode: a direct commit
    bypassed the PR/SOP flow, so it is ad-hoc by definition) → message
    stylometry (AI-looking → L2) → no_evidence_level fallback (human-typed).
    """
    level, method = classify_explicit(cfg, text=message, author=author)
    if level:
        return level, method
    if not cfg.get("smart_inference", True):
        return classify_rules(cfg, message)
    rule_level, rule_method = classify_rules(cfg, message)
    if rule_level:
        if cfg["sop_paths"]:
            return "L2", "inference:ai-without-sop-flow"
        return rule_level, rule_method
    if looks_ai_written(message):
        return "L2", "inference:ai-style-message"
    fallback = normalize_level(cfg.get("no_evidence_level") or "")
    if fallback:
        return fallback, "inference:no-ai-evidence-default"
    return None, None


@dataclass
class PrSignals:
    """Observable behaviour of a merged PR, used to infer the level."""

    author_is_bot: bool
    merged_by_bot: bool
    auto_merge: bool
    human_reviews: int  # reviews submitted by humans (any state)
    changes_requested: int  # CHANGES_REQUESTED reviews by humans
    review_threads: int  # inline review threads
    total_commits: int
    ai_commits: int  # commits whose message matches an AI rule (e.g. Claude footer)
    touches_tests: bool  # diff includes test-looking file paths
    touches_sop: bool = False  # diff includes SOP artifact paths (e.g. testcases/)
    approvals: int = 0  # human APPROVED reviews


def _is_bot(actor: dict | None, cfg: dict) -> bool:
    if not actor:
        return False
    login = actor.get("login") or ""
    return (
        actor.get("__typename") == "Bot"
        or login.endswith("[bot]")
        or login in cfg["agent_authors"]
    )


def extract_signals(node: dict, cfg: dict) -> PrSignals:
    messages = [c["commit"]["message"] for c in (node.get("commits") or {}).get("nodes", [])]
    ai_commits = sum(
        1 for m in messages
        if any(rule["contains"].lower() in m.lower() for rule in cfg["rules"])
    )
    reviews = [
        r for r in (node.get("reviews") or {}).get("nodes", [])
        if not _is_bot(r.get("author"), cfg)
    ]
    paths = [f["path"] for f in (node.get("files") or {}).get("nodes", [])]
    return PrSignals(
        author_is_bot=_is_bot(node.get("author"), cfg),
        merged_by_bot=_is_bot(node.get("mergedBy"), cfg),
        auto_merge=node.get("autoMergeRequest") is not None,
        human_reviews=len(reviews),
        changes_requested=sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED"),
        approvals=sum(1 for r in reviews if r.get("state") == "APPROVED"),
        review_threads=(node.get("reviewThreads") or {}).get("totalCount", 0),
        total_commits=len(messages),
        ai_commits=ai_commits,
        touches_tests=any(TEST_PATH_RE.search(p) for p in paths),
        touches_sop=any(
            p.startswith(prefix) for p in paths for prefix in cfg["sop_paths"]
        ),
    )


def infer_level(s: PrSignals, cfg: dict) -> tuple[str | None, str | None]:
    """Infer L1–L5 from PR behaviour. Returns (None, None) without evidence.

    The level ladder is defined by what happened *during the session*
    (human turns, who verified) — GitHub only records the residue, so this
    is an approximation. Explicit label/trailer always wins upstream.

    With `sop_paths` configured, the SOP artifact (e.g. testcases/) is the
    fingerprint of the orchestrated flow (plan → approval → tests-first →
    reviews → commit), so touching it implies L3 — even without AI footers,
    since the artifact itself is produced by the agent workflow.
    """
    checkpoints = s.changes_requested > 0 or s.review_threads > 0

    if s.author_is_bot:
        if not checkpoints and s.human_reviews == 0 and (s.merged_by_bot or s.auto_merge):
            return "L5", "inference:auto-merged-agent-pr"
        if checkpoints:
            return "L3", "inference:agent-pr-with-checkpoints"
        return "L4", "inference:agent-pr-final-review-only"

    if cfg["sop_paths"]:
        # SOP mode: testcase log present ⇒ the full flow ran ⇒ L3;
        # AI-marked commits without the artifact ⇒ ad-hoc prompting ⇒ L2.
        if s.touches_sop:
            return "L3", "inference:sop-testcase-flow"
        if s.ai_commits > 0:
            return "L2", "inference:ai-without-sop-flow"
    elif s.ai_commits > 0:
        # generic mode: human-opened PR carrying AI-marked commits
        mixed = s.ai_commits < s.total_commits
        if checkpoints or mixed:
            if mixed and not checkpoints and s.ai_commits * 2 < s.total_commits:
                return "L2", "inference:human-led-ai-assist"
            return "L3", "inference:checkpoints-or-mixed-commits"
        if s.touches_tests:
            return "L4", "inference:ai-end-to-end-with-tests"
        return "L3", "inference:ai-authored-no-tests"

    fallback = normalize_level(cfg.get("no_evidence_level") or "")
    if fallback:
        return fallback, "inference:no-ai-evidence-default"
    return None, None  # no evidence — stay unclassified


def verify_claim(level: str, s: PrSignals, additions: int, sop_configured: bool) -> str:
    """Cross-check a *claimed* level (label/trailer/author) against PR behaviour.

    GitHub-recorded human activity (reviews, threads, who opened/merged) cannot be
    faked away, so it can falsify inflated claims. The reverse is not checkable:
    in-session human steering leaves no GitHub trace, so under-claims pass silently.
    A "suspect" result never demotes the level — it flags the row for human review.
    """
    if level == "L5" and (
        not s.author_is_bot or s.human_reviews > 0 or not (s.merged_by_bot or s.auto_merge)
    ):
        return "suspect:l5-claim-on-human-pipeline"
    if level in ("L4", "L5"):
        if s.changes_requested > 0 or s.review_threads > 0:
            return "suspect:human-gates-observed"
        if 0 < s.ai_commits < s.total_commits:
            return "suspect:mixed-authorship"
        if level == "L4" and not s.touches_tests and additions > 50:
            return "suspect:no-tests-in-diff"
    if sop_configured and level in ("L3", "L4", "L5") and not s.touches_sop:
        return "suspect:sop-artifacts-missing"
    return "ok"


def resolve_branch(client: GitHubClient, owner: str, name: str, branch: str | None) -> str:
    if branch:
        return branch
    data = client.graphql(DEFAULT_BRANCH_QUERY, {"owner": owner, "name": name})
    ref = (data.get("repository") or {}).get("defaultBranchRef")
    if not ref:
        raise CollectError(f"{owner}/{name}: repo not found or empty (check token access)")
    return ref["name"]


def collect_commits(
    client: GitHubClient, repo: str, branch: str, since_iso: str, cfg: dict, skip_pr_commits: bool
) -> list[Task]:
    owner, name = repo.split("/", 1)
    tasks: list[Task] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        data = client.graphql(
            COMMITS_QUERY,
            {"owner": owner, "name": name, "expr": branch, "since": since_iso, "cursor": cursor},
        )
        obj = (data.get("repository") or {}).get("object")
        if not obj:
            raise CollectError(f"{repo}: branch '{branch}' not found")
        history = obj["history"]
        for node in history["nodes"]:
            if node["parents"]["totalCount"] > 1:
                continue  # merge commit
            if skip_pr_commits and node["associatedPullRequests"]["totalCount"] > 0:
                continue  # counted at PR granularity instead
            user = node["author"].get("user") or {}
            author = user.get("login") or node["author"].get("name") or ""
            if author in cfg["exclude_authors"]:
                continue
            level, method = classify_commit(cfg, node["message"], author)
            violations = ["direct-push-main"] if cfg.get("flag_direct_push", True) else []
            tasks.append(
                Task(
                    repo=repo,
                    kind="commit",
                    id=node["abbreviatedOid"],
                    url=node["url"],
                    date=node["committedDate"][:10],
                    title=node["message"].splitlines()[0],
                    level=level,
                    method=method,
                    additions=node["additions"],
                    deletions=node["deletions"],
                    author=author,
                    branch=branch,
                    violations=violations,
                )
            )
        if not history["pageInfo"]["hasNextPage"]:
            break
        cursor = history["pageInfo"]["endCursor"]
    return tasks


FORBIDDEN_PATH_RE = re.compile(r"(^|/)\.env$|(^|/)node_modules/|(^|/)__pycache__/")


def detect_violations(node: dict, s: PrSignals, cfg: dict, default_branch: str) -> list[str]:
    """Governance red-line checks on a merged PR (規範四 / 4.3 高風險檔)."""
    v: list[str] = []
    files = (node.get("files") or {}).get("nodes", [])
    paths = [f["path"] for f in files]
    if any(FORBIDDEN_PATH_RE.search(p) for p in paths):
        v.append("forbidden-files")
    if any(f.get("changeType") == "DELETED" and f["path"].startswith(".github/workflows/")
           for f in files):
        v.append("workflow-deleted")
    base = node.get("baseRefName")
    if base and base != default_branch:
        v.append("cross-branch-merge")
    if cfg.get("flag_unreviewed_merge", True) and s.human_reviews == 0 and not s.author_is_bot:
        v.append("merged-without-review")
    limit = cfg.get("max_pr_additions", 0)
    if limit and (node.get("additions") or 0) > limit:
        v.append("oversized-pr")
    core = cfg.get("core_paths") or []
    if core and any(p.startswith(prefix) for p in paths for prefix in core) and s.approvals < 2:
        v.append("core-without-double-review")
    return v


def _lead_hours(created: str | None, merged: str) -> float | None:
    if not created:
        return None
    delta = datetime.fromisoformat(merged) - datetime.fromisoformat(created)
    return round(delta.total_seconds() / 3600, 1)


def _ci_state(node: dict) -> str | None:
    nodes = (node.get("lastCommit") or {}).get("nodes") or [{}]
    rollup = (nodes[0].get("commit") or {}).get("statusCheckRollup") or {}
    return {"SUCCESS": "pass", "FAILURE": "fail", "ERROR": "fail"}.get(rollup.get("state"))


def collect_prs(client: GitHubClient, repo: str, since_iso: str, cfg: dict, default_branch: str = "main") -> tuple[list[Task], list[str]]:
    owner, name = repo.split("/", 1)
    tasks: list[Task] = []
    closed_unmerged: list[str] = []  # closed-without-merge dates (accept rate 分母)
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        data = client.graphql(PRS_QUERY, {"owner": owner, "name": name, "cursor": cursor})
        conn = (data.get("repository") or {}).get("pullRequests")
        if conn is None:
            raise CollectError(f"{repo}: repo not found (check token access)")
        for node in conn["nodes"]:
            if not node["mergedAt"]:
                closed_at = node.get("closedAt") or ""
                if closed_at >= since_iso:
                    closed_unmerged.append(closed_at[:10])
                continue
            if node["mergedAt"] < since_iso:
                continue
            author = (node.get("author") or {}).get("login") or ""
            if author in cfg["exclude_authors"]:
                continue
            labels = tuple(l["name"] for l in node["labels"]["nodes"])
            commit_msgs = "\n".join(
                c["commit"]["message"]
                for c in (node.get("commits") or {}).get("nodes", [])
            )
            text = f"{node['title']}\n{node.get('body') or ''}\n{commit_msgs}"
            sig = extract_signals(node, cfg)
            # ladder: label → trailer → author → inference → substring rules
            level, method = classify_explicit(cfg, labels=labels, text=text, author=author)
            check = (
                verify_claim(level, sig, node["additions"], bool(cfg["sop_paths"]))
                if level else None
            )
            if level is None and cfg.get("smart_inference", True):
                level, method = infer_level(sig, cfg)
            if level is None:
                level, method = classify_rules(cfg, text)
            tasks.append(
                Task(
                    repo=repo,
                    kind="pr",
                    id=str(node["number"]),
                    url=node["url"],
                    date=node["mergedAt"][:10],
                    title=node["title"],
                    level=level,
                    method=method,
                    additions=node["additions"],
                    deletions=node["deletions"],
                    author=author,
                    check=check,
                    branch=node.get("headRefName") or "",
                    rework=sig.changes_requested,
                    lead_hours=_lead_hours(node.get("createdAt"), node["mergedAt"]),
                    ci=_ci_state(node),
                    violations=detect_violations(node, sig, cfg, default_branch),
                )
            )
        # UPDATED_AT desc + (mergedAt <= updatedAt) => once a whole page is
        # older than the window, nothing relevant remains.
        if not conn["pageInfo"]["hasNextPage"] or all(
            n["updatedAt"] < since_iso for n in conn["nodes"]
        ):
            break
        cursor = conn["pageInfo"]["endCursor"]
    return tasks, closed_unmerged


DEFAULT_TAG_PATTERN = r"^v?\d"  # v1.2.3 / 1.0 / 2026.01 之類嘅版本 tag


def _tag_date(node: dict) -> str | None:
    """Tag date: annotated tag → tagger.date; lightweight tag → commit date."""
    target = node.get("target") or {}
    tagger = target.get("tagger") or {}
    return tagger.get("date") or target.get("committedDate")


def fetch_repo_meta(
    client: GitHubClient, repo: str, since_iso: str, tag_pattern: str = DEFAULT_TAG_PATTERN
) -> dict:
    """Window-filtered release / deployment / version-tag dates (empty on failure)."""
    owner, name = repo.split("/", 1)
    try:
        data = client.graphql(REPO_META_QUERY, {"owner": owner, "name": name})
        r = (data.get("repository") or {})
        releases = [n["publishedAt"][:10] for n in (r.get("releases") or {}).get("nodes", [])
                    if n.get("publishedAt") and n["publishedAt"] >= since_iso]
        deployments = [n["createdAt"][:10] for n in (r.get("deployments") or {}).get("nodes", [])
                       if n.get("createdAt") and n["createdAt"] >= since_iso]
        tag_re = re.compile(tag_pattern)
        tags = []
        for n in (r.get("refs") or {}).get("nodes", []):
            date = _tag_date(n)
            if date and tag_re.search(n.get("name") or "") and date[:10] >= since_iso[:10]:
                tags.append(date[:10])
        return {"releases": releases, "deployments": deployments, "tags": tags}
    except CollectError:
        return {"releases": [], "deployments": [], "tags": []}


def fetch_quality_file(client: GitHubClient, repo: str, path: str) -> dict | None:
    """Optional per-repo quality JSON maintained by the target repo's CI
    (coverage %, security finding counts, ...). None if missing/invalid."""
    try:
        return json.loads(client.rest_raw(f"/repos/{repo}/contents/{path}"))
    except (CollectError, json.JSONDecodeError):
        return None


def collect_issues(client: GitHubClient, repo: str) -> dict | None:
    """Open issues + milestone progress for the planning-side view (None on failure)."""
    owner, name = repo.split("/", 1)
    try:
        data = client.graphql(ISSUES_QUERY, {"owner": owner, "name": name})
    except CollectError:
        return None
    r = data.get("repository") or {}
    return {
        "open_total": (r.get("openIssues") or {}).get("totalCount", 0),
        "closed_total": (r.get("closedIssues") or {}).get("totalCount", 0),
        "open": [
            {
                "number": n["number"],
                "title": n["title"],
                "url": n["url"],
                "created": n["createdAt"][:10],
                "updated": n["updatedAt"][:10],
                "labels": [l["name"] for l in n["labels"]["nodes"]],
                "milestone": (n.get("milestone") or {}).get("title"),
                "due": ((n.get("milestone") or {}).get("dueOn") or "")[:10] or None,
            }
            for n in (r.get("issues") or {}).get("nodes", [])
        ],
        "milestones": [
            {
                "title": m["title"],
                "due": (m.get("dueOn") or "")[:10] or None,
                "open": m["open"]["totalCount"],
                "closed": m["closed"]["totalCount"],
            }
            for m in (r.get("milestones") or {}).get("nodes", [])
        ],
    }


def collect_repo(client: GitHubClient, repo_cfg: dict, since_iso: str, mode: str, cfg: dict) -> tuple[list[Task], dict]:
    repo = repo_cfg["name"]
    if "/" not in repo:
        raise CollectError(f"repo name must be 'owner/name', got '{repo}'")
    # per-repo overrides: a repo entry may carry its own classification knobs
    # (e.g. a known AI-assisted repo without SOP conventions)
    overrides = {
        k: repo_cfg[k]
        for k in ("no_evidence_level", "sop_paths", "rules", "agent_authors",
                  "flag_direct_push", "flag_unreviewed_merge", "max_pr_additions",
                  "core_paths", "track_issues")
        if k in repo_cfg
    }
    repo_classify = {**cfg, **overrides}
    tasks: list[Task] = []
    meta: dict = {"closed_unmerged": [], "quality": None}
    branch = resolve_branch(client, *repo.split("/", 1), repo_cfg.get("branch"))
    if mode in ("pr", "auto"):
        prs, meta["closed_unmerged"] = collect_prs(
            client, repo, since_iso, repo_classify, default_branch=branch
        )
        tasks += prs
    if mode in ("commits", "auto"):
        tasks += collect_commits(
            client, repo, branch, since_iso, repo_classify, skip_pr_commits=(mode == "auto")
        )
    meta.update(fetch_repo_meta(
        client, repo, since_iso, repo_cfg.get("tag_pattern", DEFAULT_TAG_PATTERN)
    ))
    if repo_cfg.get("quality_file"):
        meta["quality"] = fetch_quality_file(client, repo, repo_cfg["quality_file"])
    if repo_classify.get("track_issues", True):
        meta["issues"] = collect_issues(client, repo)
    return tasks, meta


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    if not raw.get("repos"):
        raise CollectError("config has no [[repos]] entries")
    classify_cfg = {**DEFAULT_CLASSIFY, **raw.get("classify", {})}
    return {
        "window_days": int(raw.get("window_days", 180)),
        "mode": raw.get("mode", "auto"),
        "repos": raw["repos"],
        "classify": classify_cfg,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--out", type=Path, default=Path("docs/data/metrics.json"))
    args = parser.parse_args(argv)

    token = os.environ.get("GH_METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("error: set GH_METRICS_TOKEN or GITHUB_TOKEN", file=sys.stderr)
        return 1

    try:
        cfg = load_config(args.config)
    except (CollectError, OSError, tomllib.TOMLDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    client = GitHubClient(token)
    since = datetime.now(timezone.utc) - timedelta(days=cfg["window_days"])
    since_iso = since.isoformat(timespec="seconds")

    tasks: list[Task] = []
    errors: list[str] = []
    repo_meta: dict = {}
    for repo_cfg in cfg["repos"]:
        try:
            got, meta = collect_repo(client, repo_cfg, since_iso, cfg["mode"], cfg["classify"])
            tasks += got
            repo_meta[repo_cfg["name"]] = meta
            print(f"  {repo_cfg['name']}: {len(got)} tasks")
        except CollectError as e:
            errors.append(str(e))
            print(f"  ! {e}", file=sys.stderr)

    if not tasks and errors:
        print("error: every repo failed", file=sys.stderr)
        return 1

    tasks.sort(key=lambda t: t.date, reverse=True)
    output = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_days": cfg["window_days"],
        "mode": cfg["mode"],
        "repos": [r["name"] for r in cfg["repos"]],
        "tasks": [asdict(t) for t in tasks],
        "repo_meta": repo_meta,
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    tagged = sum(1 for t in tasks if t.level)
    coverage = f"{tagged / len(tasks):.0%}" if tasks else "n/a"
    print(f"wrote {args.out} — {len(tasks)} tasks, level coverage {coverage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
