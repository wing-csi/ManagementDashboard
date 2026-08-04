# Project-Level Burndown Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-repo burndown chart to the 「項目 & 團隊」 tab, driven by the commit history of each repo's `plan_file`.

**Architecture:** `metrics.json` is a snapshot with no history, and a `- [x]` carries no date, so both axes must be reconstructed upstream. A new collector module walks the target repo's commits that touched `plan.md`, day-dedupes them, and re-parses each historical blob with the *existing* plan parser to produce dated `{date, done, total}` observations. The target date comes from the plan's own `due:` markers. The frontend shapes those observations into three lines (remaining, scope, ideal) and renders them with the Chart.js already loaded from CDN.

**Tech Stack:** Python 3.11+ stdlib only (`urllib`, `tomllib`), pytest + pytest-playwright, vanilla ES modules, Chart.js 4.4.1 (CDN, already present).

**Source spec:** [`specs/2026-08-04-project-burndown-chart-design.md`](../2026-08-04-project-burndown-chart-design.md)

## Global Constraints

- **No new dependencies.** Python stdlib only; no `package.json`, no build step, no new CDN script tags.
- **No new `config.toml` keys.** The feature reads only `plan_file` and `registers_ref`, which already exist.
- **`schema_version` stays `2`.** Additive fields only, matching the `people` / `owner` / `defects` precedent.
- **Do not change the return shape of `parse_plan_markdown()`** — only add keys. Four surfaces already consume it (完成度, 今日建議, 異常 tasks, Defect 追蹤).
- **`collect_github.py` must not grow substantially.** It is already 1231 lines against this repo's 800-line ceiling. New logic goes in new modules.
- **Type annotations on every new Python function signature.** PEP 8.
- **User-facing strings are Cantonese**, matching every existing card in `docs/js/`.
- **The full suite must stay green:** `python -m pytest scripts/ -q` — 274 tests pass today; every task adds to that number and none may subtract.
- **`history` is absent, never `[]`, when unavailable.** An empty array renders as a legitimately empty chart; a missing key lets the card say it could not fetch.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/collect_github.py` (modify) | Add `due_max` to `parse_plan_markdown()`; add `GitHubClient.rest_json()`; call the new history fetcher from `collect_repo()`. Nothing else. |
| `scripts/plan_history.py` (create) | Commit listing, day-dedupe, cap, per-commit blob fetch. Takes the parser by injection so it never imports `collect_github` (which imports it — circular). |
| `scripts/test_plan_history.py` (create) | Unit tests for the above. |
| `scripts/test_collect_github.py` (modify) | `due_max` cases; `collect_repo` wiring. |
| `docs/js/burndown.js` (create) | Pure shaping: observations → `{days, remaining, scope, ideal}`. No DOM. Mirrors how `aggregate.js` stays DOM-free. |
| `docs/js/render-burndown.js` (create) | DOM + Chart.js. Kept out of `render-project.js` so chart lifecycle lives with the chart. |
| `docs/index.html` (modify) | One container div in `#panel-projects`. |
| `docs/js/main.js` (modify) | One import, one call. |
| `scripts/test_burndown_js.py` (create) | Browser-evaluated unit tests for `burndown.js`, following `test_aggregate_js.py`. |
| `scripts/test_frontend_burndown.py` (create) | Playwright rendering tests, following `test_frontend_registers_ref.py`. |
| `scripts/fixtures/metrics-fixture-burndown.json` (create) | Fixture for the above. |
| `README.md` (modify) | Document the card, its inputs, and its limits. |

---

### Task 1: `due_max` in the plan parser

The chart's right edge and the ideal line's zero point. It must be computed here, not in the frontend: `plan.open_tasks` keeps only *unticked* tasks, so once the latest-dated task is ticked its `due:` disappears from `metrics.json` entirely and the deadline would jump backwards.

**Files:**
- Modify: `scripts/collect_github.py:805-844` (`parse_plan_markdown`)
- Test: `scripts/test_collect_github.py` (append)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `parse_plan_markdown(text: str) -> dict | None` gains key `"due_max": str | None` (ISO `YYYY-MM-DD`). All existing keys (`done`, `total`, `open_tasks`, `sections`) unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_collect_github.py`:

```python
PLAN_DUE_MD = """# Remediation plan

- [x] P-01 早就做完 #bug !P1 due:2026-07-10
- [ ] P-02 仲未做 #bug !P1 due:2026-08-01
- [x] P-03 做完但係最遲 #bug !P2 due:2026-09-18
"""

PLAN_HEADING_DUE_MD = """# Phase 2 due:2026-12-31

- [ ] 一件事 due:2026-08-01
- [ ] 另一件事 due:2026-08-15
"""


def test_due_max_counts_ticked_tasks():
    """打咗勾嗰個仲係最遲 due — 唔數佢,個死線會喺你 burn 緊嘅時候向前跳。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_DUE_MD)["due_max"] == "2026-09-18"


def test_due_max_prefers_a_heading_over_task_dates():
    """Heading 上面嘅 due: 係明文宣告嘅 project 死線,贏過推斷出嚟嘅最遲 task。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_HEADING_DUE_MD)["due_max"] == "2026-12-31"


def test_due_max_is_none_when_the_plan_has_no_dates():
    """冇 due: 就冇理想線 — 唔可以靜靜哋作一個出嚟。"""
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n- [x] 另一件事\n")
    assert plan["due_max"] is None


def test_due_max_sees_tasks_beyond_the_open_task_cap():
    """open_tasks 封頂 50,但 due_max 要掃晒成個檔 — 第 51 個 task
    嘅日期一樣係項目死線嘅一部分。"""
    from collect_github import parse_plan_markdown
    body = "".join(f"- [ ] task {i} due:2026-08-{i:02d}\n" for i in range(1, 29))
    body += "".join(f"- [ ] extra {i}\n" for i in range(40))
    body += "- [ ] 最後一個 due:2026-11-30\n"
    assert parse_plan_markdown("# 計劃\n\n" + body)["due_max"] == "2026-11-30"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_collect_github.py -k due_max -v
```

Expected: 4 FAILED with `KeyError: 'due_max'`.

- [ ] **Step 3: Implement**

In `scripts/collect_github.py`, edit `parse_plan_markdown`. Add two accumulators next to the existing counters:

```python
    sections: list[dict] = []
    open_tasks: list[dict] = []
    heading_dues: list[str] = []
    task_dues: list[str] = []
    cur: dict | None = None
```

In the heading branch, record the heading's date:

```python
        if h:
            m_due = PLAN_DUE_RE.search(h.group(1))
            cur_due = m_due.group(1) if m_due else None
            if cur_due:
                heading_dues.append(cur_due)
```

In the checkbox branch, search the date on **every** checkbox — before the
`if not checked` guard, so ticked tasks and tasks past the 50-item cap both count:

```python
        if m:
            total += 1
            checked = m.group(1) in "xX"
            done += checked
            raw = m.group(2)
            m_due_any = PLAN_DUE_RE.search(raw)
            if m_due_any:
                task_dues.append(m_due_any.group(1))
            if cur is not None:
                cur["total"] += 1
                cur["done"] += checked
            if not checked and len(open_tasks) < 50:
                m_due = m_due_any
                m_pri = PLAN_PRIO_RE.search(raw)
```

(The existing `raw = m.group(2)` line inside the `if not checked` block is now
redundant — delete it. `m_due` keeps its name so the `open_tasks.append(...)`
below is untouched.)

Then extend the return. ISO dates sort correctly as plain strings, so `max()` needs no date parsing:

```python
    return {"done": done, "total": total, "open_tasks": open_tasks,
            "due_max": max(heading_dues) if heading_dues else (max(task_dues) if task_dues else None),
            "sections": [s for s in sections if s["total"]][:12]}
```

Update the docstring to mention it:

```python
    """GitHub-flavored task-list plan: `- [ ]` open, `- [x]` done; headings = sections.
    Inline markers on tasks/headings: due:YYYY-MM-DD, !P0/!P1/!P2, #bug —
    task-level due overrides the section's. None if no checkboxes (not a plan).

    `due_max` is the project's target date for the burndown: a heading-level
    due: wins (an explicit declaration), else the latest date on any checkbox,
    ticked included. Counting only open tasks would walk the deadline earlier
    every time a late item lands."""
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_collect_github.py -v
```

Expected: the 4 new tests PASS and every pre-existing test in the file still passes (the return shape only gained a key).

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: parse a project due date off the plan file's own markers"
```

---

### Task 2: `plan_history.py` — commits to dated observations

**Files:**
- Create: `scripts/plan_history.py`
- Modify: `scripts/collect_github.py:281-291` (add `rest_json` next to `rest_raw`)
- Test: `scripts/test_plan_history.py`

**Interfaces:**
- Consumes: `parse_plan_markdown(text) -> dict | None` from Task 1 — passed in as the `parse` argument, never imported (`collect_github` imports this module, so importing back would be circular).
- Produces:
  - `GitHubClient.rest_json(path: str) -> list | dict` — raises `CollectError` on any HTTP/network failure.
  - `plan_history.HISTORY_CAP: int = 150`
  - `plan_history.commits_path(repo: str, path: str, ref: str | None, per_page: int = 100) -> str`
  - `plan_history.daily_commits(commits: list[dict]) -> list[tuple[str, str]]` — `(date, sha)` ascending, one per calendar day.
  - `plan_history.fetch_plan_history(client, repo: str, path: str, parse, ref: str | None = None, cap: int = HISTORY_CAP) -> dict | None` — returns `{"history": [{"date","done","total"}], "history_truncated": bool}` or `None`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_plan_history.py`:

```python
"""Unit tests for scripts/plan_history.py.

No network: the client is a stub. What is under test is the reduction from
「a repo's commit log」to「one honest observation per day」, plus the failure
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
    """上限只可以令個 flag 著 — 靜靜哋剪短條線,會令理想線嘅起點搬咗都冇人知。"""
    from plan_history import fetch_plan_history
    commits = [_commit(f"c{i}", f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}T10:00:00Z")
               for i in range(200)]
    blobs = {c["sha"]: "0/5" for c in commits}
    got = fetch_plan_history(StubClient(commits, blobs), "acme/alpha", "plan.md",
                             _parse, cap=150)
    assert len(got["history"]) == 150
    assert got["history_truncated"] is True


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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_plan_history.py -v
```

Expected: all FAIL with `ModuleNotFoundError: No module named 'plan_history'`.

- [ ] **Step 3: Implement**

Create `scripts/plan_history.py`:

```python
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
```

> **Caveat carried into the frontend (spec §4):** truncation drops the oldest
> days, so `history[0]` stops being the plan's start. The ideal line is
> anchored there, so a truncated card must say the line runs from the earliest
> *surviving* observation. Task 5 renders that caption.

Then add `rest_json` to `GitHubClient` in `scripts/collect_github.py`, directly below `rest_raw`:

```python
    def rest_json(self, path: str) -> list | dict:
        """GET a REST path returning parsed JSON (list endpoints, e.g. commits)."""
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={**self._headers, "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise CollectError(f"REST fetch {path} failed: {e}") from e
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_plan_history.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/plan_history.py scripts/test_plan_history.py scripts/collect_github.py
git commit -m "feat: reconstruct dated plan observations from plan.md commit history"
```

---

### Task 3: Wire the history into `collect_repo`

**Files:**
- Modify: `scripts/collect_github.py` — import header, and the registers block at `:1052-1057`
- Test: `scripts/test_collect_github.py` (append)

**Interfaces:**
- Consumes: `fetch_plan_history(...)` (Task 2), `parse_plan_markdown` (Task 1)
- Produces: `repo_meta[repo]["plan"]` gains **either** `"history"` + `"history_truncated"` (success) **or** `"history_error": str` (failure) — never both, and neither on old data. The frontend cannot otherwise distinguish "this run could not read the history" from "this `metrics.json` predates the feature", and those two need opposite treatment (say so vs. stay hidden).

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_collect_github.py`:

```python
def test_collect_repo_folds_plan_history_into_the_plan_block():
    from collect_github import collect_repo

    class PlanClient:
        def graphql(self, query, variables, **kw):
            return {"repository": {}}

        def rest_json(self, path):
            assert "/commits?" in path and "path=plan.md" in path
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事 due:2026-09-18\n- [x] 另一件事\n"

    _, meta = collect_repo(PlanClient(), {"name": "acme/alpha", "plan_file": "plan.md",
                                          "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["history"] == [{"date": "2026-07-28", "done": 1, "total": 2}]
    assert meta["plan"]["history_truncated"] is False
    assert meta["plan"]["due_max"] == "2026-09-18"


def test_collect_repo_omits_history_when_the_commits_call_fails():
    """缺席 ≠ 空。前端要講得出「攞唔到歷史」,而唔係畫一個空圖。"""
    from collect_github import CollectError, collect_repo

    class NoHistoryClient:
        def graphql(self, query, variables, **kw):
            return {"repository": {}}

        def rest_json(self, path):
            raise CollectError("HTTP 403")

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事\n"

    _, meta = collect_repo(NoHistoryClient(), {"name": "acme/alpha", "plan_file": "plan.md",
                                               "track_issues": False},
                           SINCE, "pr", CFG)
    assert "history" not in meta["plan"]
    assert meta["plan"]["history_error"]


def test_a_plan_without_history_support_leaves_both_keys_off():
    """舊 metrics.json 兩個 key 都冇 — 前端靠呢點分得出「讀唔到」同
    「呢份數據未有呢個 feature」,而兩者要做嘅嘢啱啱相反。"""
    from collect_github import parse_plan_markdown
    plan = parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n")
    assert "history" not in plan and "history_error" not in plan
```

> If `collect_repo` needs more of the GraphQL surface than `{"repository": {}}`
> to reach the registers block, widen `PlanClient.graphql` to return whatever
> the existing `FakeClient`-based `collect_repo` tests in this file already
> feed it — reuse those canned responses rather than inventing new ones.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_collect_github.py -k "plan_history or omits_history" -v
```

Expected: FAIL with `KeyError: 'history'`.

- [ ] **Step 3: Implement**

Add the import near the top of `scripts/collect_github.py`, after the stdlib imports:

```python
from plan_history import fetch_plan_history
```

Replace the `plan_file` branch at `scripts/collect_github.py:1054-1055`:

```python
    if repo_cfg.get("plan_file"):
        meta["plan"] = fetch_plan_file(client, repo, repo_cfg["plan_file"], registers_ref)
        if meta["plan"]:
            # Burndown 嘅時間軸:plan.md 自己嘅 commit 歷史。
            # 成功寫 history,失敗寫 history_error —— 兩者互斥。淨係靠「冇
            # history key」嘅話,一次讀唔到同一份舊 metrics.json 完全一樣,
            # 但前者要出聲、後者要收埋。
            history = fetch_plan_history(client, repo, repo_cfg["plan_file"],
                                         parse_plan_markdown, registers_ref)
            if history:
                meta["plan"].update(history)
            else:
                meta["plan"]["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/ -q
```

Expected: all pass, count = 274 baseline + 4 (Task 1) + 8 (Task 2) + 3 (Task 3) = 289.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py
git commit -m "feat: publish plan history in metrics.json"
```

---

### Task 4: `burndown.js` — observations to three lines

Pure shaping, no DOM, so it can be unit-tested the way `aggregate.js` is.

**Files:**
- Create: `docs/js/burndown.js`
- Test: `scripts/test_burndown_js.py`

**Interfaces:**
- Consumes: the `plan` object shipped by Task 3.
- Produces: `burndownSeries(plan: object, todayStr: string) -> object` with exactly these keys:
  - `status`: `'ok' | 'single-point' | 'no-history'`
  - `days`: `string[]` — every ISO date from start to end inclusive
  - `remaining`: `(number|null)[]` — `total − done`, carried forward, `null` after today
  - `scope`: `(number|null)[]` — `total`, carried forward, `null` after today
  - `ideal`: `(number|null)[]` — straight line to zero at `due`; **all null** when `due` is null
  - `todayIndex`: `number` — index of `todayStr` in `days`
  - `due`: `string|null`
  - `truncated`: `boolean`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_burndown_js.py`:

```python
"""Unit tests for docs/js/burndown.js, executed in a real browser.

Same approach as test_aggregate_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

Run:  python -m pytest scripts/test_burndown_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="burndown.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/burndown.js'); "
        f"return ({body}); }}"
    )


PLAN = """{
  path: 'plan.md', done: 3, total: 12, due_max: '2026-08-06',
  history_truncated: false,
  history: [
    {date: '2026-08-01', done: 0, total: 10},
    {date: '2026-08-03', done: 3, total: 12},
  ],
}"""


def test_remaining_carries_forward_between_observations(page, server):
    """Plan 冇改過嗰啲日唔係冇數 — 係同前一日一樣。收集端只出真實觀測,
    填平嗰段係前端嘅事。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["days"][:4] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]
    assert got["remaining"][:4] == [10, 10, 9, 9]
    assert got["scope"][:4] == [10, 10, 12, 12]


def test_the_actual_line_stops_at_today(page, server):
    """今日之後嗰段係 runway,唔係「剩返零」。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["todayIndex"] == 3
    assert got["remaining"][4:] == [None] * (len(got["days"]) - 4)


def test_the_ideal_line_reaches_zero_on_the_due_date(page, server):
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-04')")
    assert got["days"][-1] == "2026-08-06"
    assert got["ideal"][0] == 10
    assert got["ideal"][-1] == 0


def test_no_due_date_means_no_ideal_line(page, server):
    """冇 due: 就唔可以作一條死線出嚟 — 剩餘同 scope 照出。"""
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: null")
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["due"] is None
    assert all(v is None for v in got["ideal"])
    assert got["remaining"][0] == 10


def test_the_axis_still_reaches_today_when_the_due_date_has_passed(page, server):
    """遲咗嘅項目一樣要見到今日,否則個圖會喺死線度斷。"""
    got = evaluate(page, server, f"m.burndownSeries({PLAN}, '2026-08-20')")
    assert got["days"][-1] == "2026-08-20"


def test_a_single_observation_is_flagged_not_drawn_as_a_trend(page, server):
    plan = """{path: 'plan.md', done: 0, total: 5, due_max: '2026-09-01',
               history_truncated: false,
               history: [{date: '2026-08-01', done: 0, total: 5}]}"""
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["status"] == "single-point"


def test_a_missing_history_key_is_not_an_empty_chart(page, server):
    plan = "{path: 'plan.md', done: 3, total: 12, due_max: '2026-09-01'}"
    got = evaluate(page, server, f"m.burndownSeries({plan}, '2026-08-04')")
    assert got["status"] == "no-history"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_burndown_js.py -v
```

Expected: FAIL — the dynamic `import('/js/burndown.js')` rejects because the file does not exist.

- [ ] **Step 3: Implement**

Create `docs/js/burndown.js`:

```js
/** 項目 burndown 嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  收集端只出「plan.md 真係改過嗰啲日」嘅觀測(見 scripts/plan_history.py)。
 *  中間嗰啲平坦日子喺呢度 carry-forward 補返:焗入 JSON 嘅話,一條階梯函數
 *  同真正嘅每日取樣就完全分唔開。
 */

const DAY = 864e5;
const toMs = (s) => new Date(s + 'T00:00:00Z').getTime();
const toISO = (ms) => new Date(ms).toISOString().slice(0, 10);

/** start..end(包頭包尾)每一日嘅 ISO 日期。 */
function dayRange(start, end) {
  const out = [];
  for (let ms = toMs(start); ms <= toMs(end); ms += DAY) out.push(toISO(ms));
  return out;
}

export function burndownSeries(plan, todayStr) {
  const history = (plan || {}).history;
  if (!Array.isArray(history) || history.length === 0) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, truncated: false };
  }

  const start = history[0].date;
  const due = plan.due_max || null;
  // 死線過咗都要見到今日,否則個圖會喺死線度斷;ISO 日期直接字串比大細。
  const lastObs = history[history.length - 1].date;
  const end = [due || lastObs, lastObs, todayStr].sort().pop();
  const days = dayRange(start, end);

  const byDate = new Map(history.map((h) => [h.date, h]));
  const todayIndex = days.indexOf(todayStr);
  const remaining = [];
  const scope = [];
  let cur = null;
  days.forEach((d, i) => {
    if (byDate.has(d)) cur = byDate.get(d);
    const past = todayIndex < 0 || i <= todayIndex;
    remaining.push(past && cur ? cur.total - cur.done : null);
    scope.push(past && cur ? cur.total : null);
  });

  // 理想線錨喺起點嘅 scope,唔係今日嘅 —— scope 加咗幾多,就係兩條線嘅開叉。
  const dueIndex = due ? days.indexOf(due) : -1;
  const startTotal = history[0].total;
  const ideal = days.map((_, i) => {
    if (dueIndex <= 0 || i > dueIndex) return null;
    return +(startTotal * (1 - i / dueIndex)).toFixed(2);
  });

  return {
    status: history.length === 1 ? 'single-point' : 'ok',
    days, remaining, scope, ideal, todayIndex, due,
    truncated: !!plan.history_truncated,
  };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_burndown_js.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/js/burndown.js scripts/test_burndown_js.py
git commit -m "feat: shape plan observations into remaining, scope and ideal lines"
```

---

### Task 5: Render the burndown cards

**Files:**
- Create: `docs/js/render-burndown.js`
- Modify: `docs/index.html` — inside `#panel-projects`, immediately after `<div id="projMilestones"></div>` (line 214)
- Modify: `docs/js/main.js` — import beside line 8, call beside line 33
- Test: `scripts/test_frontend_burndown.py`, `scripts/fixtures/metrics-fixture-burndown.json`

**Interfaces:**
- Consumes: `burndownSeries(plan, todayStr)` (Task 4); `state`, `$`, `esc`, `repoInScope` from `./data.js`
- Produces: `renderBurndown(): void`, exported from `docs/js/render-burndown.js`

- [ ] **Step 1: Write the failing tests**

Create the fixture `scripts/fixtures/metrics-fixture-burndown.json` by copying
`scripts/fixtures/metrics-fixture-defects.json`, setting its top-level
`"generated_at"` to `"2026-08-04T00:00:00+00:00"` so today is deterministic, and
adding this `plan` block to `repo_meta["acme/alpha"]`:

```json
{
  "done": 3, "total": 12, "path": "plan.md", "ref": null,
  "due_max": "2026-08-06", "history_truncated": false,
  "sections": [{"title": "Phase 2", "done": 3, "total": 12}],
  "open_tasks": [],
  "history": [
    {"date": "2026-08-01", "done": 0, "total": 10},
    {"date": "2026-08-03", "done": 3, "total": 12}
  ]
}
```

Create `scripts/test_frontend_burndown.py`:

```python
"""項目 burndown 卡嘅渲染守則。

每個空狀態都要各有講法:冇圖嘅時候一定要講得出點解,唔可以留一格白,
亦唔可以畫一條假線。呢個係成張卡最容易靜靜哋出錯嘅地方。

Run:  python -m pytest scripts/test_frontend_burndown.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="burndown rendering tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture-burndown.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _serve(page, data: dict) -> None:
    page.route(
        "**/data/metrics.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(data, ensure_ascii=False)),
    )


def _open(page, server):
    page.goto(f"{server}/", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def test_a_repo_with_plan_history_gets_a_chart(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert dash.eval_on_selector_all("#burndownCards canvas", "els => els.length") == 1


def test_a_failed_history_fetch_says_so_instead_of_drawing_a_flat_line(page, server):
    """讀唔到就要出聲。一條平線同一張消失咗嘅卡都係當「冇嘢做緊」,兩個都呃人。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["history"]
    plan["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .burndown-card", state="attached")
    assert dash.eval_on_selector_all("#burndownCards canvas", "els => els.length") == 0
    assert "攞唔到" in dash.inner_text("#burndownCards")


def test_a_plan_without_a_due_date_says_why_there_is_no_ideal_line(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = None
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "冇理想線" in dash.inner_text("#burndownCards")


def test_a_single_observation_says_it_is_not_a_trend_yet(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["history"] = [
        {"date": "2026-08-01", "done": 0, "total": 10}]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "未成趨勢" in dash.inner_text("#burndownCards")


def test_a_truncated_history_says_the_ideal_line_moved(page, server):
    """截斷掉走最舊嗰批,理想線就唔再由項目開頭拉出嚟 — 唔講嘅話條線係呃人。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["history_truncated"] = True
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "已截斷" in dash.inner_text("#burndownCards")


def test_old_metrics_without_any_plan_history_hide_the_section(page, server):
    """向後兼容:舊 metrics.json 兩個 key 都冇,成個 section 收埋,唔係報錯,
    亦唔會當佢係「讀唔到」而出一張錯嘅卡。"""
    data = _load()
    for meta in data["repo_meta"].values():
        meta.pop("plan", None)
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0


def test_today_is_marked_on_the_chart(page, server):
    """今日條線係「追唔追得上」嘅參考點 —— 冇佢,兩條線嘅開叉讀唔出意思。"""
    data = _load()
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    drawn = dash.evaluate(
        "() => Chart.getChart(document.querySelector('#burndownCards canvas'))"
        ".options.plugins.todayMarker.index")
    assert drawn == 3  # fixture: 2026-08-01 起,今日 2026-08-04
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_frontend_burndown.py -v
```

Expected: FAIL — `#burndownCards` does not exist.

- [ ] **Step 3: Implement**

Add the container to `docs/index.html`, immediately after `<div id="projMilestones"></div>`:

```html
      <div id="burndownCards"></div>
```

Create `docs/js/render-burndown.js`:

```js
import { state, $, esc, repoInScope } from './data.js';
import { burndownSeries } from './burndown.js';

/** 每個 repo 一個 Chart 實例。state.chart 得一個位,係每週圖嘅;
 *  唔另開一本帳,重畫嗰陣舊 canvas 會漏返出嚟。 */
const charts = new Map();

const CAPTION = {
  'single-point': '只有一個觀測點,未成趨勢',
};

/** 今日嗰條直線。Chart.js 4 冇內置 annotation,但一個 inline plugin
 *  就夠 —— 為咗一條線裝多個 CDN library 唔抵。 */
const todayMarker = {
  id: 'todayMarker',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts || opts.index == null || opts.index < 0) return;
    const x = chart.scales.x.getPixelForValue(opts.index);
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = '#C4553B';
    ctx.lineWidth = 1;
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.restore();
  },
};

function captionFor(series) {
  const bits = [];
  if (CAPTION[series.status]) bits.push(CAPTION[series.status]);
  if (!series.due) bits.push('plan.md 冇 due: — 冇理想線');
  if (series.truncated) bits.push('歷史已截斷,理想線由現存最早嗰個觀測起計');
  return bits.join(' · ');
}

export function renderBurndown() {
  const box = $('burndownCards');
  if (!box) return;
  for (const chart of charts.values()) chart.destroy();
  charts.clear();
  box.innerHTML = '';

  const today = state.data.generated_at.slice(0, 10);
  const rm = state.data.repo_meta || {};
  for (const [repo, meta] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const plan = meta.plan;
    // 兩個 key 都冇 = 舊 metrics.json,成張卡唔出。history_error 有 = 今次
    // 讀唔到,出張卡講明 —— 靜靜哋消失同畫一條平線一樣咁誤導。
    if (!plan || (!plan.history_error && !(plan.history || []).length)) continue;

    const series = burndownSeries(plan, today);
    const caption = plan.history_error || captionFor(series);
    const card = document.createElement('div');
    card.className = 'burndown-card';
    card.innerHTML = `<div class="t">${esc(repo.split('/').pop())}
        <span style="color:var(--muted)">· burndown(${esc(plan.path)})</span></div>
      ${plan.history_error ? '' : '<div class="chart-box"><canvas></canvas></div>'}
      ${caption ? `<div class="note" style="color:var(--muted)">${esc(caption)}</div>` : ''}`;
    box.appendChild(card);

    if (plan.history_error) continue;            // 冇數據,冇圖,但有交代
    if (typeof Chart === 'undefined') continue;  // CDN 未 load 到,唔好阻住其他區塊
    charts.set(repo, new Chart(card.querySelector('canvas'), {
      type: 'line',
      plugins: [todayMarker],
      data: {
        labels: series.days.map((d) => d.slice(5)),
        datasets: [
          { label: '剩餘', data: series.remaining, borderColor: '#1F3A5F',
            pointRadius: 0, borderWidth: 2, tension: 0, spanGaps: false },
          { label: '總 scope', data: series.scope, borderColor: '#8FA8CB',
            pointRadius: 0, borderWidth: 1.5, borderDash: [2, 2], tension: 0 },
          { label: '理想', data: series.ideal, borderColor: '#9AA5A0',
            pointRadius: 0, borderWidth: 1.5, borderDash: [6, 4], tension: 0 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom',
                    labels: { boxWidth: 10, boxHeight: 10, padding: 12 } },
          todayMarker: { index: series.todayIndex },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 },
               title: { display: true, text: 'tasks 剩餘' } },
        },
      },
    }));
  }
}
```

Wire it into `docs/js/main.js` — add the import beside the other render imports:

```js
import { renderBurndown } from './render-burndown.js';
```

and call it directly after `renderProjects();`:

```js
  renderProjects();
  renderBurndown();
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_frontend_burndown.py -v
```

Then the whole suite:

```bash
python -m pytest scripts/ -q
```

Expected: the 7 new tests PASS and the suite is green. If
`test_frontend_snapshot.py` fails, the rendered baseline changed on purpose —
re-record it with `python -m pytest scripts/test_frontend_snapshot.py --snapshot-update`
and read the diff before committing.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/js/main.js docs/js/render-burndown.js scripts/test_frontend_burndown.py scripts/fixtures/metrics-fixture-burndown.json
git commit -m "feat: burndown card per plan repo in the projects tab"
```

---

### Task 6: Document the card

**Files:**
- Modify: `README.md` — the 「項目進度(Issues / Milestones)」 section, after the 完成度 bullet list

**Interfaces:**
- Consumes: everything above. Produces no code.

- [ ] **Step 1: Write the section**

Insert into `README.md` after the bullet list ending 「見到 % 跌,先問「係咪開咗新 issues」,唔好直接當退步。」:

````markdown
### 項目 Burndown

設咗 `plan_file` 嘅 repo,每個喺「項目 & 團隊」多一張 burndown 卡。**唔使加任何 config** — 兩條軸都由已有嘅嘢讀返嚟:

| 軸 | 來源 |
|---|---|
| 起點同每一點 | target repo 入面 `plan.md` 嘅 **commit 歷史**(每日最後一個 commit,經同一個 parser 重新讀一次) |
| 目標日 | `plan.md` 自己嘅 `due:` — heading 上面嗰個優先,否則取全部 checkbox 最遲嗰個(**打咗勾嘅照計**) |

三條線:**剩餘**(`total − done`,觀測之間拉平)、**總 scope**(`total`)、**理想**(由起點 scope 直線落到目標日嘅 0)。總 scope 條線係故意要有嘅 —— 完成度 % 回跌通常係 scope 浮現,唔係退步,冇呢條線個現象只會令人誤會。

同「項目進度」一樣,burndown **唔跟** window selector(30/60/90/180)。

**讀之前要知:**

- **解像度 = `plan.md` 嘅 commit 頻率。** 一星期 commit 一次就一星期一點。個檔幾時改過,係我哋唯一真正觀測到嘅嘢。
- **`plan.md` 開檔之前嘅嘢睇唔到。** 起點係第一個 commit,唔係項目真正開始嗰日。
- **目標日多數係推斷出嚟**(最遲嗰個 task due),除非有人喺 heading 明文寫。想寫死就喺 heading 加 `due:YYYY-MM-DD`。
- **重寫過歷史(force push / squash)嘅 plan branch 會失真** —— commits API 只見到現存嘅 history。
- 登記冊住喺自己條 branch 嘅話,`registers_ref` 一樣管住 burndown —— ref 錯咗 commits API 派**空** list,而空 list 會當「冇歷史」,卡直接唔出。
````

- [ ] **Step 2: Verify the docs match the code**

```bash
python -m pytest scripts/ -q
```

Expected: green. Then read the new README section against `docs/js/burndown.js`
and `scripts/plan_history.py` and confirm every claim holds — in particular that
ticked tasks count toward `due_max`, and that nothing in `render-burndown.js`
consults `state.windowDays`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the project burndown card and its limits"
```

---

## Verification

Before opening a PR:

```bash
python -m pytest scripts/ -q
```

Expected: 274 baseline + 4 (Task 1) + 8 (Task 2) + 3 (Task 3) + 7 (Task 4) + 7 (Task 5) = **303 passed**.

Then look at it for real. The collector needs a token, so this is the honest end-to-end check:

```bash
python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
```

```bash
python3 -m http.server -d docs 8000
```

Open <http://localhost:8000>, go to 「項目 & 團隊」, and confirm AIFlowTesting's card
appears with an ideal line ending at `2026-09-18` — its latest `due:`, on P-11.
`docs/data/metrics.json` is gitignored; do not commit it.
