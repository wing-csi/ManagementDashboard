"""Unit tests for scripts/plan_history.py.

No network: the client is a stub. What is under test is the reduction from
「a repo's commit log」to「一日一個誠實嘅觀測」, plus the failure
contract — an unreachable history must read as absent, never as empty.

Run:  python -m pytest scripts/test_plan_history.py -v
"""

from __future__ import annotations

import sys
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
