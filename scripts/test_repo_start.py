"""Unit tests for scripts/repo_start.py.

No network: the client is a stub. What is under test is the two-request walk
to the *oldest* commit — GitHub serves commits newest-first and has no
"oldest" endpoint, so the page count in the `Link` header is the only route
there. The failure contract matters as much as the happy path: an unreadable
repo must read as absent, never as the newest commit wearing the oldest
one's hat.

Run:  python -m pytest scripts/test_repo_start.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


class StubError(Exception):
    """Stands in for CollectError — first_commit_date catches broadly."""


def _commit(sha: str, date: str) -> dict:
    return {"sha": sha, "commit": {"committer": {"date": date}}}


def _link(page: int, rel: str) -> str:
    return (f'<https://api.github.com/repositories/1/commits'
            f'?per_page=1&page={page}>; rel="{rel}"')


class StubClient:
    """Serves one commit per page, plus that page's Link header."""

    def __init__(self, pages: dict[int, list], links: dict[int, str],
                 error_on: set[int] | None = None):
        self.pages = pages
        self.links = links
        self.error_on = error_on or set()
        self.paths: list[str] = []

    def rest_json_links(self, path: str):
        self.paths.append(path)
        page = int(path.rsplit("page=", 1)[-1])
        if page in self.error_on:
            raise StubError("HTTP 409")
        return self.pages.get(page, []), self.links.get(page, "")


def test_the_oldest_commit_comes_from_the_last_page():
    """Commit list 係新到舊,所以最舊嗰個喺最後一版。版數淨係 Link 度有。"""
    from repo_start import first_commit_date
    client = StubClient(
        pages={1: [_commit("new", "2026-08-01T10:00:00Z")],
               57: [_commit("old", "2026-05-03T08:30:00Z")]},
        links={1: _link(2, "next") + ", " + _link(57, "last")},
    )
    assert first_commit_date(client, "acme/alpha") == "2026-05-03"
    assert client.paths == ["/repos/acme/alpha/commits?per_page=1&page=1",
                            "/repos/acme/alpha/commits?per_page=1&page=57"]


def test_a_repo_with_one_commit_needs_no_second_request():
    """冇 Link = 冇下一版。`per_page=1` 之下即係得一個 commit,手上嗰個
    就係佢 —— 再問一次係白費一個 request。"""
    from repo_start import first_commit_date
    client = StubClient(pages={1: [_commit("only", "2026-06-16T00:00:00Z")]},
                        links={})
    assert first_commit_date(client, "acme/alpha") == "2026-06-16"
    assert len(client.paths) == 1


def test_the_default_branch_is_used_not_a_ref():
    """呢個答緊「個 repo 幾時開檔」,唔係「plan 條 branch 幾時開檔」——
    後者已經係 plan_history 行緊嘅嘢。"""
    from repo_start import first_commit_date
    client = StubClient(pages={1: [_commit("only", "2026-06-16T00:00:00Z")]},
                        links={})
    first_commit_date(client, "acme/alpha")
    assert "sha=" not in client.paths[0]


def test_an_unreadable_repo_is_none_not_a_guess():
    """空 repo 出 409。攞唔到就係攞唔到 —— caller 會跌返落第一個觀測。"""
    from repo_start import first_commit_date
    client = StubClient(pages={}, links={}, error_on={1})
    assert first_commit_date(client, "acme/alpha") is None


def test_a_failure_on_the_last_page_is_none_too():
    """第一版攞到手,但佢係**最新**嗰個 commit。攞唔到最後一版就寧願冇,
    唔可以攞手上嗰個頂替 —— 咁樣會將今日當成開檔日。"""
    from repo_start import first_commit_date
    client = StubClient(
        pages={1: [_commit("new", "2026-08-01T10:00:00Z")]},
        links={1: _link(57, "last")},
        error_on={57},
    )
    assert first_commit_date(client, "acme/alpha") is None


def test_a_link_header_with_next_but_no_last_is_none():
    """有下一版但講唔出總共幾多版 = 揾唔到最舊嗰個。回手上嗰個嘅話,
    個 dashboard 會靜靜哋話你聽個項目今日先開檔。"""
    from repo_start import first_commit_date
    client = StubClient(pages={1: [_commit("new", "2026-08-01T10:00:00Z")]},
                        links={1: _link(2, "next")})
    assert first_commit_date(client, "acme/alpha") is None


def test_an_empty_page_is_none():
    """一個 commit 都冇嘅 repo。"""
    from repo_start import first_commit_date
    assert first_commit_date(StubClient(pages={1: []}, links={}), "acme/alpha") is None


def test_a_commit_without_a_committer_date_is_none():
    """Payload 缺欄位唔可以變成一個 crash,亦唔可以變成一個空字串日期。"""
    from repo_start import first_commit_date
    client = StubClient(pages={1: [{"sha": "x"}]}, links={})
    assert first_commit_date(client, "acme/alpha") is None


def test_the_last_page_regex_is_not_fooled_by_per_page():
    """`per_page=1` 入面都有 'page='。夾錯咗就會去攞第 1 版,即係最新
    嗰個 commit,而且完全冇徵狀。"""
    from repo_start import LAST_PAGE_RE
    m = LAST_PAGE_RE.search(_link(2, "next") + ", " + _link(57, "last"))
    assert m and m.group(1) == "57"
