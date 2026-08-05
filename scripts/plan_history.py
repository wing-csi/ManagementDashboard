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
PER_PAGE = 100  # GitHub 嘅硬上限:list endpoint 一版最多派 100 個
# 100 × 20 = 2000 個 commit,遠遠夠冚 150 個觀測日;純粹係封住死循環嘅閘,
# 唔係常態。同 collect_github.MAX_PAGES 一樣係 20,但嗰個係 GraphQL 嘅,
# 兩邊各有各嘅 transport,唔可以共用一個常數扮成同一件事。
MAX_HISTORY_PAGES = 20


class _Client(Protocol):
    def rest_json(self, path: str) -> list | dict: ...
    def rest_raw(self, path: str) -> str: ...


def commits_path(repo: str, path: str, ref: str | None,
                 per_page: int = PER_PAGE, page: int = 1) -> str:
    """Commits that touched `path`, pinned to `ref` when the plan has its own branch.

    Same contract as `collect_github._contents_path()`: no `sha` means GitHub
    serves the default branch, which is correct for a plan living on `main`.
    A *wrong* ref returns an empty list rather than an error, which is why the
    caller must treat empty as「揾唔到」and not as「冇歷史」.

    `per_page` 頂到 100 就冇得再大 —— 想攞多過 100 個 commit 唯一嘅方法係
    揭下一版,所以呢度一定要出 `page`,見 `_fetch_commit_pages()`。
    """
    query = [f"path={urllib.parse.quote(path)}", f"per_page={per_page}",
             f"page={page}"]
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


def _fetch_commit_pages(
    client: _Client,
    repo: str,
    path: str,
    ref: str | None,
    cap: int,
    per_page: int = PER_PAGE,
    max_pages: int = MAX_HISTORY_PAGES,
) -> tuple[list[dict], bool]:
    """一版一版揭,直到夠料為止。回 (commits, 上游仲有嘢未攞)。

    一個 request 得 100 個 commit,即係最多 100 個日曆日 —— 一份改過超過
    100 次嘅 plan,`commits[-1]` 就唔再係開檔嗰個 commit,而理想線正正錨喺
    `history[0]` 嘅 scope。所以呢度一定要揭版:150 日嘅上限先至係真上限,
    `history_truncated` 先至係「真係剪咗嘢」嘅意思。

    停喺三個位:短版(到底)、日數已經多過 cap(最新 cap 日已經齊,再舊
    嘅點反正都要剪走)、或者揭到 `max_pages`。最後嗰種先至係唯一一個「攞
    唔晒」嘅出口,所以佢要老實認 truncated。
    """
    commits: list[dict] = []
    for page in range(1, max_pages + 1):
        try:
            batch = client.rest_json(commits_path(repo, path, ref, per_page, page))
        except Exception:
            if page == 1:
                raise  # 第一版都攞唔到 = 真係讀唔到歷史,唔可以扮成「歷史係空」
            # 中途斷線:攞到幾多用幾多,但條線嘅頭係唔完整嘅,要認。
            return commits, True
        if not isinstance(batch, list) or not batch:
            return commits, False  # 空版 = 冇下一版
        commits.extend(batch)
        if len(batch) < per_page:
            return commits, False  # 短版 = 已經到底
        if len(daily_commits(commits)) > cap:
            return commits, False  # 夠 cap+1 日,最新嗰 cap 日已經完整
    return commits, True


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
        commits, more_upstream = _fetch_commit_pages(client, repo, path, ref, cap)
    except Exception:
        return None
    if not commits:
        return None

    days = daily_commits(commits)
    if not days:
        return None
    # 兩個都係「`history[0]` 唔再係開檔嗰日」:日數過咗 cap(我哋自己剪),
    # 或者揭到版數上限都仲有更舊嘅(攞唔晒)。後者理論上可能全部都係已經
    # 見過嘅日子,但唔再發 request 係查唔到嘅 —— 寧願講多咗,都好過條理想線
    # 扮成由項目開頭拉出嚟。
    truncated = len(days) > cap or more_upstream
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
