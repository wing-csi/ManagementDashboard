#!/usr/bin/env python3
"""The date of a repo's first commit, for plans that do not declare a start.

`plan.md`'s history starts the day the plan file was first committed, which
is often weeks after the project itself — AIFlowTesting's axis began
2026-07-28, the day `plan.md` became a checklist, while the repo already had
a tag from 2026-06-16. When the plan declares no `start:`, the repo's own
first commit is the next best answer.

GitHub has no "oldest commit" endpoint. The commit list is newest-first, so
the oldest one sits on the last page — and the only place that page count
exists is the `Link` header. Two requests, whatever the repo's size.

The client is injected for the same reason as `plan_history.py`:
`collect_github` imports this module, so importing it back would be circular.
"""

from __future__ import annotations

import re
from typing import Protocol

# `[^>]*` 唔會過到個 `>`,所以佢夾唔穿去下一段 URL;而 `[?&]` 擋住
# `per_page=1` 入面嗰個 "page="(佢前面係 `_`)。任何一個夾錯咗,我哋就會
# 去攞第 1 版 —— 即係最新嗰個 commit —— 而且完全冇徵狀。
LAST_PAGE_RE = re.compile(r'[?&]page=(\d+)[^>]*>;\s*rel="last"')
HAS_NEXT_RE = re.compile(r'rel="next"')


class _Client(Protocol):
    def rest_json_links(self, path: str) -> tuple[list | dict, str]: ...


def commits_page(repo: str, page: int) -> str:
    """一版一個 commit。冇 `sha`,即係 GitHub 派 default branch。

    Default branch 係**刻意**嘅:呢度答緊「個 repo 幾時開檔」,唔係
    「plan 條 branch 幾時開檔」—— 後者已經係 `plan_history` 行緊嘅嘢。
    """
    return f"/repos/{repo}/commits?per_page=1&page={page}"


def _commit_date(payload: list | dict) -> str | None:
    """Payload 第一個 commit 嘅日期(`YYYY-MM-DD`),缺任何一層都出 None。"""
    if not isinstance(payload, list) or not payload:
        return None
    stamp = (((payload[0].get("commit") or {}).get("committer") or {})
             .get("date") or "")[:10]
    return stamp or None


def first_commit_date(client: _Client, repo: str) -> str | None:
    """`YYYY-MM-DD` of the repo's oldest commit on the default branch.

    None — never a guess — when it cannot be read: an empty repo (409), a
    network failure, or a `Link` header that announces more pages without
    saying how many. The caller falls back to the first plan observation,
    which is always available.

    That last case is the one worth spelling out. Page 1 is in hand, but it
    holds the *newest* commit. Returning it would date the project to today
    and look entirely plausible on the chart — the worst kind of wrong.
    """
    try:
        first, link = client.rest_json_links(commits_page(repo, 1))
    except Exception:
        return None
    link = link or ""
    m = LAST_PAGE_RE.search(link)
    if not m:
        # 冇 rel="last" 又冇 rel="next" = 得一版,手上嗰個就係唯一嗰個。
        # 有 next 但冇 last = 講唔出去邊度攞,唯有認冇。
        return None if HAS_NEXT_RE.search(link) else _commit_date(first)
    try:
        oldest, _ = client.rest_json_links(commits_page(repo, int(m.group(1))))
    except Exception:
        return None
    return _commit_date(oldest)
