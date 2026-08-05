"""Unit tests for scripts/plan_history.py.

No network: the client is a stub. What is under test is the reduction from
「a repo's commit log」to「一日一個誠實嘅觀測」, plus the failure
contract — an unreachable history must read as absent, never as empty.

Run:  python -m pytest scripts/test_plan_history.py -v
"""

from __future__ import annotations

import datetime
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


class StubError(Exception):
    """Stands in for CollectError — fetch_plan_history catches broadly."""


def _commit(sha: str, date: str) -> dict:
    return {"sha": sha, "commit": {"committer": {"date": date}}}


def _parse(text: str) -> dict | None:
    """Stand-in for parse_plan_markdown: the blob body encodes 'done/total'."""
    done, total = text.split("/")
    return {"done": int(done), "total": int(total)}


class StubClient:
    """Serves a canned commit list, then a blob per sha."""

    def __init__(self, commits: list[dict], blobs: dict[str, str],
                 commits_error: bool = False):
        self.commits = commits
        self.blobs = blobs
        self.commits_error = commits_error
        self.paths: list[str] = []

    def rest_json(self, path: str):
        self.paths.append(path)
        if self.commits_error:
            raise StubError("HTTP 404")
        return self.commits

    def rest_raw(self, path: str) -> str:
        self.paths.append(path)
        sha = path.rsplit("=", 1)[-1]
        if sha not in self.blobs:
            raise StubError("HTTP 404")
        return self.blobs[sha]


def _day(n: int) -> str:
    """由 2026-01-01 起計第 n 日,行真日曆。"""
    return (datetime.date(2026, 1, 1) + datetime.timedelta(days=n)).isoformat()


class PagedStubClient:
    """真實嘅 REST 分頁:一版最多 `per_page` 個,最後一版短。

    上面嗰個 StubClient 一次 call 就派晒成個 commit list,所以佢由頭到尾
    都撞唔到傳輸層嗰個 100 上限 —— 分頁完全冇寫都照樣綠。呢個 stub 就係
    補返嗰忽:commit 由新到舊排(同 GitHub 一樣),要多過 100 個就一定要
    揭版先攞得到。
    """

    def __init__(self, commits: list[dict], blobs: dict[str, str],
                 fail_on_page: int | None = None):
        self.commits = commits
        self.blobs = blobs
        self.fail_on_page = fail_on_page
        self.pages: list[int] = []

    def rest_json(self, path: str):
        query = urllib.parse.parse_qs(path.split("?", 1)[1])
        page = int(query["page"][0])
        per_page = int(query["per_page"][0])
        assert per_page <= 100, "GitHub list endpoint 一版派唔到多過 100 個"
        self.pages.append(page)
        if page == self.fail_on_page:
            raise StubError("HTTP 502")
        return self.commits[(page - 1) * per_page:page * per_page]

    def rest_raw(self, path: str) -> str:
        sha = path.rsplit("=", 1)[-1]
        if sha not in self.blobs:
            raise StubError("HTTP 404")
        return self.blobs[sha]


def _paged(n_days: int, per_day: int = 1) -> PagedStubClient:
    """n_days 個日曆日,每日 per_day 個 commit,由新到舊。"""
    commits = [_commit(f"c{day}-{k}", f"{_day(day)}T{10 + k:02d}:00:00Z")
               for day in range(n_days - 1, -1, -1)
               for k in range(per_day - 1, -1, -1)]
    return PagedStubClient(commits, {c["sha"]: "0/5" for c in commits})


def test_commits_path_pins_the_ref_when_the_plan_lives_on_a_branch():
    from plan_history import commits_path
    got = commits_path("acme/alpha", "plan.md", "docs/registers")
    assert "path=plan.md" in got
    assert "sha=docs/registers" in got


def test_commits_path_omits_the_ref_on_the_default_branch():
    """AIFlowTesting 冇設 registers_ref — 帶一個空 sha 落去會攞到零個 commit。"""
    from plan_history import commits_path
    assert "sha=" not in commits_path("acme/alpha", "plan.md", None)


def test_daily_commits_keeps_the_last_commit_of_each_day():
    """GitHub 派最新行先,所以每日第一個見到嘅就係嗰日收工嗰個。"""
    from plan_history import daily_commits
    got = daily_commits([
        _commit("c3", "2026-08-02T18:00:00Z"),
        _commit("c2", "2026-08-02T09:00:00Z"),
        _commit("c1", "2026-07-28T10:00:00Z"),
    ])
    assert got == [("2026-07-28", "c1"), ("2026-08-02", "c3")]


def test_fetch_plan_history_returns_ascending_observations():
    from plan_history import fetch_plan_history
    client = StubClient(
        [_commit("c2", "2026-08-02T09:00:00Z"), _commit("c1", "2026-07-28T10:00:00Z")],
        {"c1": "0/11", "c2": "3/12"},
    )
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse)
    assert got["history"] == [
        {"date": "2026-07-28", "done": 0, "total": 11},
        {"date": "2026-08-02", "done": 3, "total": 12},
    ]
    assert got["history_truncated"] is False


def test_fetch_plan_history_caps_and_flags_truncation():
    """上限只可以令個 flag 著 — 靜靜哋剪短條線,會令理想線嘅起點搬咗都冇人知。

    200 個 commit,每個佔一個獨立日曆日,由 2026-01-01 排到 2026-08-04。
    冚到淨番 150 個,一定係剪走最舊嗰 50 日,而唔係剪走最新嗰啲 —
    如果實作剪錯頭,呢兩條邊界斷言就會斷。
    """
    from plan_history import fetch_plan_history
    commits = [_commit(f"c{i}", f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}T10:00:00Z")
               for i in range(200)]
    blobs = {c["sha"]: "0/5" for c in commits}
    got = fetch_plan_history(StubClient(commits, blobs), "acme/alpha", "plan.md",
                             _parse, cap=150)
    assert len(got["history"]) == 150
    assert got["history_truncated"] is True
    # 剪走最舊 50 日 (2026-01-01..2026-02-22),留低最新 150 日。
    assert got["history"][0]["date"] == "2026-02-23"
    assert got["history"][-1]["date"] == "2026-08-04"


# ------------------------------------------------------- 分頁(傳輸層上限)


def test_commits_path_carries_a_page_number():
    """`per_page` 頂到 100 —— 想要多過 100 個 commit,`page` 係唯一嘅路。"""
    from plan_history import commits_path
    assert "page=1" in commits_path("acme/alpha", "plan.md", None)
    assert "page=3" in commits_path("acme/alpha", "plan.md", None, 100, 3)


def test_fetch_plan_history_pages_past_the_hundred_commit_ceiling():
    """一個 request 得 100 個 commit,即係最多 100 個日曆日。

    唔揭版嘅話,一份改過 130 次嘅 plan 就會靜靜哋淨返最新 100 日,而
    `history[0]`(理想線嘅錨)就唔再係項目起點 —— 冇任何 flag 著,冇人知。
    """
    from plan_history import fetch_plan_history
    client = _paged(130)
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse, cap=150)
    assert len(got["history"]) == 130
    assert got["history"][0]["date"] == _day(0)      # 真係由開檔嗰日起
    assert got["history"][-1]["date"] == _day(129)
    assert got["history_truncated"] is False         # 150 未撞到,冇剪過嘢
    assert client.pages == [1, 2]                    # 第二版短,收工


def test_fetch_plan_history_flags_truncation_only_when_the_cap_really_bites():
    """150 先至係真上限。200 日 → 剪走最舊 50 日,flag 著。"""
    from plan_history import fetch_plan_history
    got = fetch_plan_history(_paged(200), "acme/alpha", "plan.md", _parse, cap=150)
    assert len(got["history"]) == 150
    assert got["history_truncated"] is True
    assert got["history"][0]["date"] == _day(50)     # 剪頭唔剪尾
    assert got["history"][-1]["date"] == _day(199)


def test_a_short_plan_is_never_flagged_as_truncated():
    """一版就攞得晒嘅 plan,無論如何都唔可以標「已截斷」—— 標錯咗就係叫
    人以為條理想線搬咗位,同靜靜哋搬位一樣咁誤導。"""
    from plan_history import fetch_plan_history
    client = _paged(12)
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse, cap=150)
    assert len(got["history"]) == 12
    assert got["history_truncated"] is False
    assert client.pages == [1]


def test_fetch_plan_history_stops_at_the_page_limit_and_admits_it():
    """病態 repo(2100 個 commit 擠喺 105 日)唔可以行到天光。

    揭到版數上限就收手,但上游仲有更舊嘅 commit,`history[0]` 因此唔一定
    係開檔嗰日 —— 呢個出口一定要認 truncated,否則就係另一種靜靜哋剪短。
    """
    from plan_history import MAX_HISTORY_PAGES, fetch_plan_history
    client = _paged(105, per_day=20)
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse, cap=150)
    assert len(client.pages) == MAX_HISTORY_PAGES
    assert got["history_truncated"] is True
    assert len(got["history"]) == 100  # 2000 個 commit ÷ 每日 20 個


def test_a_failure_midway_through_paging_keeps_what_it_got_and_admits_it():
    """第一版之後先斷 = 攞到嘅仍然係最新嗰段真數據,掉咗佢冇著數;但條線
    嘅頭係唔完整嘅,所以要 flag,唔可以扮完整。"""
    from plan_history import fetch_plan_history
    client = _paged(250, per_day=2)  # 一版 100 個 commit = 50 日
    client.fail_on_page = 3
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse, cap=150)
    assert client.pages == [1, 2, 3]                 # 真係試過揭第三版
    assert got["history_truncated"] is True
    assert len(got["history"]) == 100                # 頭兩版嘅 100 日
    assert got["history"][-1]["date"] == _day(249)   # 最新嗰邊完好


def test_fetch_plan_history_is_none_when_the_commits_call_fails():
    from plan_history import fetch_plan_history
    assert fetch_plan_history(StubClient([], {}, commits_error=True),
                              "acme/alpha", "plan.md", _parse) is None


def test_fetch_plan_history_is_none_when_there_are_no_commits():
    """空 commit list 唔係「歷史係空」,係「呢個 path / ref 揾唔到嘢」。
    回 [] 會令前端畫一個合法但係空嘅圖。"""
    from plan_history import fetch_plan_history
    assert fetch_plan_history(StubClient([], {}), "acme/alpha", "plan.md", _parse) is None


def test_one_unreadable_blob_does_not_kill_the_series():
    from plan_history import fetch_plan_history
    client = StubClient(
        [_commit("c2", "2026-08-02T09:00:00Z"), _commit("c1", "2026-07-28T10:00:00Z")],
        {"c1": "0/11"},  # c2 缺席
    )
    got = fetch_plan_history(client, "acme/alpha", "plan.md", _parse)
    assert got["history"] == [{"date": "2026-07-28", "done": 0, "total": 11}]


def test_fetch_plan_history_is_none_when_every_blob_is_unreadable():
    """日子唔係空,但每個 blob 都攞唔到 — 呢個仍然係「攞唔到歷史」,
    唔可以扮成「歷史係空」畀前端畫一張睇落合法但乜都冇講嘅圖。"""
    from plan_history import fetch_plan_history
    client = StubClient(
        [_commit("c1", "2026-07-28T10:00:00Z")], {},  # 呢個 commit 嘅 blob 唔存在
    )
    assert fetch_plan_history(client, "acme/alpha", "plan.md", _parse) is None
