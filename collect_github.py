#!/usr/bin/env python3
"""Collect commits and merged PRs from GitHub repos and classify AI-Level.

Reads a TOML config listing repos, pulls history via the GitHub GraphQL API,
classifies each task's autonomy level (L1–L5), and writes a flat task list
that docs/index.html aggregates client-side.

Classification priority (first match wins):
    1. PR label            e.g. ai-level/L3
    2. Trailer in message  e.g. "AI-Level: L3" in commit message or PR body
    3. Author mapping      config [classify.author_levels]
    4. Heuristic rules     config [[classify.rules]] substring match

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
        number title body mergedAt updatedAt additions deletions url
        author{ login }
        labels(first:20){ nodes{ name } }
      }
    }
  }
}"""


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
    method: str | None  # "label" | "trailer" | "author" | "rule" | None
    additions: int
    deletions: int
    author: str


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


def classify(
    cfg: dict, *, labels: tuple[str, ...] = (), text: str = "", author: str = ""
) -> tuple[str | None, str | None]:
    """Return (level, method) using the priority ladder described above."""
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

    lowered = text.lower()
    for rule in cfg["rules"]:
        if rule["contains"].lower() in lowered:
            level = normalize_level(rule["level"])
            if level:
                return level, "rule"
    return None, None


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
            text = f"{node['title']}\n{node.get('body') or ''}"
            level, method = classify(cfg, labels=labels, text=text, author=author)
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
