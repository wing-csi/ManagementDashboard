#!/usr/bin/env python3
"""Dated observations of a plan file, reconstructed from its commit history.

`metrics.json` is a snapshot, and a `- [x]` records what is done but never
when. The one place the timing survives is the target repo's own git history:
every commit that touched `plan.md` is a dated snapshot of that plan. Walking
it is retroactive — the first run already has the full series — and stateless,
so a re-run reproduces the same line rather than appending to a file that can
drift.

The parser is injected rather than imported: `collect_github` imports this
module, so importing it back would be circular. It also means these tests need
no GitHub types at all.
"""

from __future__ import annotations

import urllib.parse
from typing import Callable, Protocol

HISTORY_CAP = 150


class _Client(Protocol):
    def rest_json(self, path: str) -> list | dict: ...
    def rest_raw(self, path: str) -> str: ...


def commits_path(repo: str, path: str, ref: str | None,
                 per_page: int = 100) -> str:
    """Commits that touched `path`, pinned to `ref` when the plan has its own branch.

    Same contract as `collect_github._contents_path()`: no `sha` means GitHub
    serves the default branch, which is correct for a plan living on `main`.
    A *wrong* ref returns an empty list rather than an error, which is why the
    caller must treat empty as「揾唔到」and not as「冇歷史」.
    """
    query = [f"path={urllib.parse.quote(path)}", f"per_page={per_page}"]
    if ref:
        query.append(f"sha={urllib.parse.quote(ref, safe='/')}")
    return f"/repos/{repo}/commits?" + "&".join(query)


def daily_commits(commits: list[dict]) -> list[tuple[str, str]]:
    """(date, sha) for the last commit of each calendar day, ascending.

    GitHub returns newest first, so the first entry seen for a day is that
    day's final state. One point per day is the right resolution: a burndown
    reads by date, and three commits on one afternoon are one observation.
    """
    by_day: dict[str, str] = {}
    for commit in commits:
        date = (((commit.get("commit") or {}).get("committer") or {})
                .get("date") or "")[:10]
        sha = commit.get("sha")
        if not date or not sha or date in by_day:
            continue
        by_day[date] = sha
    return sorted(by_day.items())


def fetch_plan_history(
    client: _Client,
    repo: str,
    path: str,
    parse: Callable[[str], dict | None],
    ref: str | None = None,
    cap: int = HISTORY_CAP,
) -> dict | None:
    """Dated `{date, done, total}` observations, ascending.

    None — not an empty list — when the history cannot be read at all. The
    frontend has to tell「攞唔到歷史」apart from「歷史係空」: the first is a
    card that explains itself, the second is a chart that looks legitimate and
    says nothing true.

    Only days the plan actually changed become points. Padding the flat days
    here would make a step function indistinguishable from real daily
    sampling, at several times the payload for no added information — the
    frontend carries values forward instead.
    """
    try:
        commits = client.rest_json(commits_path(repo, path, ref))
    except Exception:
        return None
    if not isinstance(commits, list) or not commits:
        return None

    days = daily_commits(commits)
    if not days:
        return None
    truncated = len(days) > cap
    days = days[-cap:]  # keep the most recent; see the caveat below

    history: list[dict] = []
    for date, sha in days:
        blob_path = f"/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={sha}"
        try:
            plan = parse(client.rest_raw(blob_path))
        except Exception:
            continue  # one bad blob is a missing point, not a dead series
        if plan:
            history.append({"date": date, "done": plan["done"],
                            "total": plan["total"]})
    if not history:
        return None
    return {"history": history, "history_truncated": truncated}
