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
from dataclasses import asdict, dataclass
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
    pullRequests(states:MERGED, first:50, orderBy:{field:UPDATED_AT, direction:DESC}, after:$cursor){
      pageInfo{ hasNextPage endCursor }
      nodes{
        number title body mergedAt updatedAt additions deletions url headRefName
        author{ login __typename }
        mergedBy{ login __typename }
        autoMergeRequest{ enabledBy{ login } }
        reviews(first:50){ nodes{ state author{ login __typename } } }
        reviewThreads(first:1){ totalCount }
        labels(first:20){ nodes{ name } }
        commits(first:50){ nodes{ commit{ message } } }
        files(first:100){ nodes{ path } }
      }
    }
  }
}"""

TEST_PATH_RE = re.compile(
    r"(^|/)tests?/|(^|/)test_|_test\.|\.test\.|\.spec\.|Test\.java$|Tests\.java$|Spec\."
)


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
            level, method = classify(cfg, text=node["message"], author=author)
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
                )
            )
        if not history["pageInfo"]["hasNextPage"]:
            break
        cursor = history["pageInfo"]["endCursor"]
    return tasks


def collect_prs(client: GitHubClient, repo: str, since_iso: str, cfg: dict) -> list[Task]:
    owner, name = repo.split("/", 1)
    tasks: list[Task] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        data = client.graphql(PRS_QUERY, {"owner": owner, "name": name, "cursor": cursor})
        conn = (data.get("repository") or {}).get("pullRequests")
        if conn is None:
            raise CollectError(f"{repo}: repo not found (check token access)")
        for node in conn["nodes"]:
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
                )
            )
        # UPDATED_AT desc + (mergedAt <= updatedAt) => once a whole page is
        # older than the window, nothing relevant remains.
        if not conn["pageInfo"]["hasNextPage"] or all(
            n["updatedAt"] < since_iso for n in conn["nodes"]
        ):
            break
        cursor = conn["pageInfo"]["endCursor"]
    return tasks


def collect_repo(client: GitHubClient, repo_cfg: dict, since_iso: str, mode: str, cfg: dict) -> list[Task]:
    repo = repo_cfg["name"]
    if "/" not in repo:
        raise CollectError(f"repo name must be 'owner/name', got '{repo}'")
    tasks: list[Task] = []
    if mode in ("pr", "auto"):
        tasks += collect_prs(client, repo, since_iso, cfg)
    if mode in ("commits", "auto"):
        branch = resolve_branch(client, *repo.split("/", 1), repo_cfg.get("branch"))
        tasks += collect_commits(
            client, repo, branch, since_iso, cfg, skip_pr_commits=(mode == "auto")
        )
    return tasks


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
    for repo_cfg in cfg["repos"]:
        try:
            got = collect_repo(client, repo_cfg, since_iso, cfg["mode"], cfg["classify"])
            tasks += got
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
