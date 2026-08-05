# Plan 起點三層 Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 條 burndown 軸嘅起點由「第一日改過 `plan.md`」改為三層 fallback —— `plan.md` 宣告嘅 `start:` → repo 第一個 commit → 第一個 plan 觀測 —— 令理想線同 SPI 唔再因為 plan 檔開得遲而偏樂觀。

**Architecture:** 起點嘅決定完全住喺 `resolvePlanWindow()`(`docs/js/plan-dates.js`)一個地方,burndown 同 timeline 兩張圖照舊由佢攞 `start`。收集端加兩個 optional 欄位餵佢:`plan.start_min`(新 `start:` marker)同 `plan.repo_first_commit`(新 module `scripts/repo_start.py`,兩個 REST request)。兩個欄位缺席就跌返今日嘅行為。

**Tech Stack:** Vanilla ES modules,冇 build step。Python 3.11+ stdlib(`urllib`、`re`)。pytest + pytest-playwright。

**Source spec:** [`specs/2026-08-05-plan-start-date-design.md`](../2026-08-05-plan-start-date-design.md)

## Global Constraints

- **冇新 dependency。** 冇 `package.json`、冇 build step、冇新 CDN `<script>`。收集端只用 stdlib。
- **`schema_version` 維持 `2`。** `start_min` 同 `repo_first_commit` 兩個都係 optional:舊 `metrics.json` 兩個都冇,前端要行返今日一模一樣嘅路。
- **`history` 依然係硬前提。** 零觀測 = 零卡(`no-history`)。三層永遠跌得落地,因為 `history[0].date` 永遠喺度。
- **`startReason` 只講人手宣告嘅嘢。** `repo_first_commit` 唔係人手寫嘅,攞唔到 / 唔啱就靜靜跌落下一層 —— 出一句叫人去改乜嘢都冇。
- **Collector 嘅 stderr warning 一律 ASCII。** `scripts/test_collect_github.py::test_an_invalid_due_is_reported_not_dropped_in_silence` 有 `assert err.isascii()`,呢啲字會出 Windows console。
- **用家見到嘅字係廣東話**,同 `docs/js/` 每張卡一致。
- **`docs/js/` 唔准出現 `font-size` px 字面值**(`scripts/test_frontend_typography.py` 當文字 regex,連註解都夾)。
- **`repo_start.py` 唔可以 import `collect_github`。** `collect_github` import 佢,反過嚟就循環 —— 同 `plan_history.py` 一樣用注入 client。
- **全套測試要保持綠色:** `python -m pytest scripts/ -q` —— 今日 **369 passed**(行足 12 分鐘)。每個 task 只加唔減。
- **逐個 task 只行嗰個 task 嘅測試檔**,全套留返最尾行一次。

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/collect_github.py`(改) | `PLAN_START_RE`、`_calendar_dues()` → `_calendar_dates()`、`_clean_plan_title()`、`parse_plan_markdown()` 出 `start_min`、`GitHubClient.rest_json_links()`、`collect_repo()` 寫 `repo_first_commit` |
| `scripts/repo_start.py`(新) | `first_commit_date(client, repo)` —— 兩個 REST request + `Link` header 解析。純邏輯,注入 client |
| `docs/js/plan-dates.js`(改) | 三層解析 + `startSource` / `startReason` |
| `docs/js/burndown.js`(改) | 兩個新欄位 pass-through(渲染層要讀) |
| `docs/js/timeline.js`(改) | 同上,連 `EMPTY` |
| `docs/js/render-burndown.js`(改) | 起點出處 + `startReason` 兩句 + `due-not-after-start` 改字 + truncated 句加條件 |
| `docs/js/render-timeline.js`(改) | `NO_SPI['due-not-after-start']` 改字 |
| `scripts/test_repo_start.py`(新) | `first_commit_date()` 單元測試,stub client |
| `scripts/test_collect_github.py`(改) | `start:` 解析 + `collect_repo` 寫欄位 |
| `scripts/test_plan_dates_js.py`(改) | 三層優先次序 + 兩個 reason |
| `scripts/test_burndown_js.py`(改) | 起點到第一個觀測留白 + 理想線錨 |
| `scripts/test_timeline_js.py`(改) | SPI 用新起點 |
| `scripts/test_frontend_burndown.py`(改) | Caption 字句 |
| `scripts/test_frontend_timeline.py`(改) | `NO_SPI` 字句 |
| `scripts/fixtures/metrics-fixture-burndown.json`(改) | 加兩個新欄位 |
| `README.md`(改) | 寫低 `start:` marker |

依賴單向:`plan-dates.js` ← `burndown.js` / `timeline.js` ← `render-*.js`。
`repo_start.py` 同 `plan_history.py` 平排,兩個都唔識 `collect_github`。

> **設計文件同呢份 plan 有一處唔同,以呢份為準。** Spec §6 寫住 `burndown.js`
> 同 `timeline.js`「唔改」。實際上唔得:`render-burndown.js` 要讀
> `series.startSource`,而 `burndownSeries()` 個 return object 冇 pass 過佢。
> 兩個檔各加一行 pass-through,見 Task 4。

---

### Task 1: `start:` marker → `plan.start_min`

**Files:**
- Modify: `scripts/collect_github.py`(`:807` 加 regex、`:812-816` `_clean_plan_title`、`:819-847` `_calendar_dues`、`:850-909` `parse_plan_markdown`)
- Test: `scripts/test_collect_github.py`(`# ---- plan history` 分隔線之前加)

**Interfaces:**
- Consumes: 冇(第一個 task)
- Produces:
  - `PLAN_START_RE: re.Pattern` —— `\bstart:(\d{4}-\d{2}-\d{2})\b`
  - `_calendar_dates(values: list[str], source: str, marker: str) -> list[str]` —— 取代 `_calendar_dues(values, source)`
  - `parse_plan_markdown(...)` 個 dict 多一個 key:`start_min: str | None`

- [ ] **Step 1: 寫住會 fail 嘅測試**

加喺 `scripts/test_collect_github.py`,`test_due_max_sees_tasks_beyond_the_open_task_cap` 之後:

```python
PLAN_START_MD = """# Issue board start:2026-06-16 due:2026-09-18

- [x] 做咗嘅嘢
- [ ] 未做嘅嘢
"""


def test_a_heading_start_becomes_start_min():
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_START_MD)["start_min"] == "2026-06-16"


def test_a_plan_without_start_has_none():
    """冇宣告唔係一個錯 —— 前端會跌落下一層,唔使喺呢度作一個日期出嚟。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown("# 計劃\n\n- [ ] 一件事\n")["start_min"] is None


def test_the_earliest_heading_start_wins():
    """`due:` 取 max、`start:` 取 min —— 兩個一齊圍出最闊嘅宣告窗口。"""
    from collect_github import parse_plan_markdown
    md = ("# 第一期 start:2026-06-16\n\n- [ ] 一件事\n\n"
          "# 第二期 start:2026-07-01\n\n- [ ] 另一件事\n")
    assert parse_plan_markdown(md)["start_min"] == "2026-06-16"


def test_a_task_level_start_is_not_a_project_start():
    """一個 task 幾時開始唔係項目起點。`due:` 收 task 級係因為要砌 marker,
    起點冇呢個需要 —— 收咗就會有人喺一行 checkbox 度改到成條軸。"""
    from collect_github import parse_plan_markdown
    md = "# 計劃\n\n- [ ] 一件事 start:2026-06-16\n"
    assert parse_plan_markdown(md)["start_min"] is None


def test_a_start_that_is_not_a_calendar_date_is_dropped():
    """同 due: 一樣,個 regex 淨係夾 shape。`2026-02-30` 過得 regex,
    但 JS 會靜靜哋當佢係 3 月 2 日,喺條軸上面永遠 indexOf 唔到。"""
    from collect_github import parse_plan_markdown
    md = "# 計劃 start:2026-02-30\n\n- [ ] 一件事\n"
    assert parse_plan_markdown(md)["start_min"] is None


def test_a_dropped_start_warns_under_its_own_marker_name(capsys):
    """兩個 marker 唔可以共用一句講 due_max 嘅說話 —— 睇嘅人要知去改邊個字。"""
    from collect_github import parse_plan_markdown
    parse_plan_markdown("# 計劃 start:2026-02-30\n\n- [ ] 一件事\n",
                        "acme/alpha plan.md")
    err = capsys.readouterr().err
    assert "acme/alpha plan.md" in err
    assert "start:2026-02-30" in err
    assert "due" not in err
    assert err.isascii(), "呢啲字會出去 Windows console,非 ASCII 會變亂碼"


def test_start_is_stripped_from_the_section_title():
    """唔 strip 嘅話個 section title 會帶住 `start:2026-06-16` 出街。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_START_MD)["sections"][0]["title"] == "Issue board"


def test_the_due_side_still_behaves_after_the_rename():
    """`_calendar_dues` → `_calendar_dates` 係一個純改名 —— due 嗰邊
    一個字都唔應該變。"""
    from collect_github import parse_plan_markdown
    assert parse_plan_markdown(PLAN_BAD_DUE_MD)["due_max"] == "2026-09-18"
```

- [ ] **Step 2: 行測試,確認佢 fail**

```bash
python -m pytest scripts/test_collect_github.py -k "start_min or heading_start or task_level_start or dropped_start or start_is_stripped or after_the_rename" -v
```

Expected: FAIL —— `KeyError: 'start_min'`。

- [ ] **Step 3: 落實作**

`scripts/collect_github.py:807` 之後加:

```python
PLAN_START_RE = re.compile(r"\bstart:(\d{4}-\d{2}-\d{2})\b")
```

`_clean_plan_title()` 加多一行(同 `PLAN_DUE_RE` 唔重疊,前後都得):

```python
def _clean_plan_title(text: str) -> str:
    text = PLAN_START_RE.sub("", text)
    text = PLAN_DUE_RE.sub("", text)
    text = PLAN_PRIO_RE.sub("", text)
    text = PLAN_BUG_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()
```

`_calendar_dues` 整個換成:

```python
# 一個爛日期喺兩個 marker 度造成嘅傷害唔同,所以句 warning 唔可以共用。
# ASCII only: 呢度出去 Windows console,非 cp1252 字元會變成問號。
_MARKER_HARM = {
    "due": "it would win max() and become the burndown deadline",
    "start": "it would win min() and become the burndown start",
}


def _calendar_dates(values: list[str], source: str, marker: str) -> list[str]:
    """Drop `<marker>:` dates that do not exist on the calendar, loudly.

    The marker regexes only match the *shape* `\\d{4}-\\d{2}-\\d{2}`, and both
    `due_max` and `start_min` reduce with a plain string `max()`/`min()` — so
    one typo outranks every valid date in the same year ('2026-13-01' >
    '2026-09-18' for due; '1900-01-01' < everything for start) and becomes the
    project window. The frontend then parses it to NaN and draws a card with a
    title, a blank chart and nothing to explain it. `plan.md` is hand-edited in
    the *target* repo, so this is untrusted input crossing a boundary and has to
    be validated here, not assumed.

    `source` names the repo/file for the warning; empty means「唔好嘈」and is
    what the history replay passes — the same bad line sits in all 150 old
    blobs of the same file, and the operator only has one file to fix.
    """
    kept: list[str] = []
    for value in values:
        try:
            date.fromisoformat(value)
        except ValueError:
            if source:
                print(f"  ! warning: {source} has {marker}:{value} - not a real "
                      f"calendar date, ignored ({_MARKER_HARM[marker]})",
                      file=sys.stderr)
            continue
        kept.append(value)
    return kept
```

`parse_plan_markdown()` 入面四處:

```python
    sections: list[dict] = []
    open_tasks: list[dict] = []
    heading_dues: list[str] = []
    heading_starts: list[str] = []          # <- 新
    task_dues: list[str] = []
```

```python
        h = HEADING_RE.match(line)
        if h:
            m_due = PLAN_DUE_RE.search(h.group(1))
            cur_due = m_due.group(1) if m_due else None
            if cur_due:
                heading_dues.append(cur_due)
            m_start = PLAN_START_RE.search(h.group(1))    # <- 新
            if m_start:                                    # <- 新
                heading_starts.append(m_start.group(1))    # <- 新
            cur = {"title": _clean_plan_title(h.group(1)), "done": 0, "total": 0}
```

```python
    heading_dues = _calendar_dates(heading_dues, source, "due")
    task_dues = _calendar_dates(task_dues, source, "due")
    heading_starts = _calendar_dates(heading_starts, source, "start")
    return {"done": done, "total": total, "open_tasks": open_tasks,
            "due_max": max(heading_dues) if heading_dues else (max(task_dues) if task_dues else None),
            "start_min": min(heading_starts) if heading_starts else None,
            "sections": [s for s in sections if s["total"]][:12]}
```

同埋 `parse_plan_markdown` docstring 嗰句 `see \`_calendar_dues()\`` 改做
`_calendar_dates()`,再加一句講 `start_min`:

```python
    `start_min` is the declared project start: the earliest heading-level
    `start:`. Heading level only — a task's start date is not the project's.
```

- [ ] **Step 4: 行測試,確認全部綠**

```bash
python -m pytest scripts/test_collect_github.py -q
```

Expected: PASS,一個 fail 都冇(現有嗰批 due 測試要一齊綠)。

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py && git commit -m "feat: parse a heading-level start: marker into plan.start_min"
```

---

### Task 2: `repo_start.py` —— repo 第一個 commit

**Files:**
- Create: `scripts/repo_start.py`
- Create: `scripts/test_repo_start.py`
- Modify: `scripts/collect_github.py`(`GitHubClient`,`rest_json()` 之後,`:305` 附近)

**Interfaces:**
- Consumes: 冇(獨立於 Task 1)
- Produces:
  - `GitHubClient.rest_json_links(path: str) -> tuple[list | dict, str]` —— `(parsed JSON, Link header)`,header 缺席出 `""`
  - `repo_start.first_commit_date(client, repo: str) -> str | None` —— `YYYY-MM-DD`
  - `repo_start.commits_page(repo: str, page: int) -> str`
  - `repo_start.LAST_PAGE_RE: re.Pattern`

- [ ] **Step 1: 寫住會 fail 嘅測試**

新檔 `scripts/test_repo_start.py`:

```python
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
```

- [ ] **Step 2: 行測試,確認佢 fail**

```bash
python -m pytest scripts/test_repo_start.py -v
```

Expected: FAIL —— `ModuleNotFoundError: No module named 'repo_start'`。

- [ ] **Step 3: 落實作**

新檔 `scripts/repo_start.py`:

```python
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
# `per_page=1` 入面嗰個 "page="(佢前面係 `_`)。任何一個夾錯咗,我哋
# 就會去攞第 1 版 —— 即係最新嗰個 commit —— 而且完全冇徵狀。
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
```

`scripts/collect_github.py`,`rest_json()` 之後(`:305` 附近)加:

```python
    def rest_json_links(self, path: str) -> tuple[list | dict, str]:
        """GET a REST path, returning (parsed JSON, the `Link` response header).

        `rest_json()` throws the headers away, and a list endpoint's page count
        lives nowhere else — so「最舊嗰個 commit 喺第幾版」is unanswerable
        without this. `Link` is absent on single-page responses; `""` then.
        """
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={**self._headers, "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode()), resp.headers.get("Link", "")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise CollectError(f"REST fetch {path} failed: {e}") from e
```

- [ ] **Step 4: 行測試,確認全部綠**

```bash
python -m pytest scripts/test_repo_start.py scripts/test_collect_github.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/repo_start.py scripts/test_repo_start.py scripts/collect_github.py && git commit -m "feat: resolve a repo's first commit date via the Link header"
```

---

### Task 3: 接落 `collect_repo()` → `plan.repo_first_commit`

**Files:**
- Modify: `scripts/collect_github.py`(import 區、`collect_repo()` `:1120-1132`)
- Test: `scripts/test_collect_github.py`(`test_collect_repo_omits_history_when_the_commits_call_fails` 之後)

**Interfaces:**
- Consumes: `repo_start.first_commit_date(client, repo)`(Task 2)
- Produces: `repo_meta[<repo>]["plan"]["repo_first_commit"]: str | None`

- [ ] **Step 1: 寫住會 fail 嘅測試**

```python
def test_collect_repo_records_the_repo_first_commit():
    """條軸嘅 C 層後備。冇佢嘅話,一個開檔咗半年、上個月先開 plan.md
    嘅項目,條軸會由上個月起計。"""
    from collect_github import DEFAULT_BRANCH_QUERY, PRS_QUERY, collect_repo

    class FirstCommitClient:
        def graphql(self, query, variables, **kw):
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_json_links(self, path):
            if path.endswith("page=1"):
                return ([{"sha": "new",
                          "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}],
                        '<https://api.github.com/repositories/1/commits'
                        '?per_page=1&page=9>; rel="last"')
            return ([{"sha": "old",
                      "commit": {"committer": {"date": "2026-05-03T08:00:00Z"}}}], "")

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事 due:2026-09-18\n"

    _, meta = collect_repo(FirstCommitClient(),
                           {"name": "acme/alpha", "plan_file": "plan.md",
                            "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["repo_first_commit"] == "2026-05-03"


def test_an_unreadable_first_commit_leaves_the_key_null_not_missing():
    """None 同「攞唔到」喺前端係同一件事(跌落下一層),但 key 要在,
    先分得出「呢份數據行過呢段代碼」同「呢份數據舊過呢個 feature」。"""
    from collect_github import (CollectError, DEFAULT_BRANCH_QUERY, PRS_QUERY,
                                collect_repo)

    class NoFirstCommitClient:
        def graphql(self, query, variables, **kw):
            if query == DEFAULT_BRANCH_QUERY:
                return DEFAULT_BRANCH_RESP
            if query == PRS_QUERY:
                return prs_page([])
            return {"repository": {}}

        def rest_json(self, path):
            return [{"sha": "c1", "commit": {"committer": {"date": "2026-07-28T10:00:00Z"}}}]

        def rest_json_links(self, path):
            raise CollectError("HTTP 409")

        def rest_raw(self, path):
            return "# 計劃\n\n- [ ] 一件事\n"

    _, meta = collect_repo(NoFirstCommitClient(),
                           {"name": "acme/alpha", "plan_file": "plan.md",
                            "track_issues": False},
                           SINCE, "pr", CFG)
    assert meta["plan"]["repo_first_commit"] is None
```

現有兩個 stub client(`PlanClient`、`NoHistoryClient`)都冇 `rest_json_links`。
`first_commit_date()` 會撞 `AttributeError` 然後靜靜哋出 `None` —— 測試照樣綠,
但係綠得唔明不白。兩個 class 各加一行講清楚:

```python
        def rest_json_links(self, path):
            return [], ""   # 呢兩個 test 唔關 repo 開檔日事
```

- [ ] **Step 2: 行測試,確認佢 fail**

```bash
python -m pytest scripts/test_collect_github.py -k "first_commit" -v
```

Expected: FAIL —— `KeyError: 'repo_first_commit'`。

- [ ] **Step 3: 落實作**

`scripts/collect_github.py` import 區(`from plan_history import ...` 隔籬)加:

```python
from repo_start import first_commit_date
```

`collect_repo()` `:1120-1132` 嗰段改成:

```python
    if repo_cfg.get("plan_file"):
        meta["plan"] = fetch_plan_file(client, repo, repo_cfg["plan_file"], registers_ref)
        if meta["plan"]:
            # Burndown 嘅時間軸:plan.md 自己嘅 commit 歷史。
            # 成功寫 history,失敗寫 history_error —— 兩者互斥。淨係靠「冇
            # history key」嘅話,一次讀唔到同一份舊 metrics.json 完全一樣,
            # 而兩者要做嘅嘢啱啱相反。
            history = fetch_plan_history(client, repo, repo_cfg["plan_file"],
                                         parse_plan_markdown, registers_ref)
            if history:
                meta["plan"].update(history)
            else:
                meta["plan"]["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
            # 條軸起點嘅 C 層後備,plan.md 冇宣告 `start:` 嗰陣用。兩個
            # REST request,所以淨係喺真係有 plan 嘅 repo 度畀 —— 冇 plan
            # 嘅 repo 攞返嚟都冇人讀。
            meta["plan"]["repo_first_commit"] = first_commit_date(client, repo)
```

- [ ] **Step 4: 行測試,確認全部綠**

```bash
python -m pytest scripts/test_collect_github.py scripts/test_repo_start.py scripts/test_plan_history.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_github.py scripts/test_collect_github.py && git commit -m "feat: record each plan repo's first commit date in metrics.json"
```

---

### Task 4: `resolvePlanWindow()` 三層解析

**Files:**
- Modify: `docs/js/plan-dates.js`(`:56-77` `resolvePlanWindow`)
- Modify: `docs/js/burndown.js`(`:14` 解構、`:15-19` 同 `:52-56` 兩個 return)
- Modify: `docs/js/timeline.js`(`:21-26` `EMPTY`、`:29` 解構、`:91-100` return)
- Test: `scripts/test_plan_dates_js.py`、`scripts/test_burndown_js.py`、`scripts/test_timeline_js.py`

**Interfaces:**
- Consumes: `plan.start_min`、`plan.repo_first_commit`(Task 1、3)
- Produces:
  - `resolvePlanWindow(plan) -> {start, startSource, startReason, due, dueReason}`
    - `startSource` ∈ `'plan' | 'repo' | 'observation' | null`(`null` 淨係喺 `no-history`)
    - `startReason` ∈ `'start-unusable' | 'start-after-history' | null`
  - `burndownSeries(plan, today)` 個 return object 多咗 `startSource`、`startReason`
  - `timelineStrip(plan, today)` 同上

- [ ] **Step 1: 寫住會 fail 嘅測試**

`scripts/test_plan_dates_js.py` 檔尾加:

```python
FULL = HIST + ", start_min: '2026-06-16', repo_first_commit: '2026-05-03'"


def test_a_declared_start_wins_over_the_repo_and_the_observation(page, server):
    got = evaluate(page, server, f"m.resolvePlanWindow({{{FULL}}})")
    assert got["start"] == "2026-06-16"
    assert got["startSource"] == "plan"
    assert got["startReason"] is None


def test_without_a_declared_start_the_repo_first_commit_is_used(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, repo_first_commit: '2026-05-03'}})")
    assert got["start"] == "2026-05-03"
    assert got["startSource"] == "repo"
    assert got["startReason"] is None


def test_an_old_metrics_json_still_starts_at_the_first_observation(page, server):
    """兩個 key 都冇 = 舊數據。行為要同呢個 feature 之前一模一樣。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] is None


def test_a_start_that_is_not_a_calendar_date_falls_through_and_says_so(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, start_min: '2026-02-30', "
                   "repo_first_commit: '2026-05-03'}})")
    assert got["start"] == "2026-05-03"
    assert got["startSource"] == "repo"
    assert got["startReason"] == "start-unusable"


def test_a_month_thirteen_start_is_unusable_not_late(page, server):
    """`'2026-13-01' > '2026-08-01'` 係字串比大細,答「係」,但佢唔係遲咗 ——
    佢根本唔係一個日期。揀錯咗個 reason,張卡就會叫人去改一個唔存在嘅問題。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}, start_min: '2026-13-01'}})")
    assert got["startReason"] == "start-unusable"


def test_a_start_far_enough_back_to_blow_the_axis_is_unusable_too(page, server):
    """`realDate('1900-01-01')` 係真,但 dayRange() 會生四萬幾個日期,
    而佢個 cap 係剪尾 —— 剪走今日同死線。同 due-unusable 一樣一句過。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}, start_min: '1900-01-01'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] == "start-unusable"


def test_a_start_later_than_the_first_observation_is_not_believed(page, server):
    """plan.md 話八月三號開始,但 git 話八月一號已經 commit 過呢份 plan。
    採用佢就要切走一個真係量度過嘅觀測點,而個圖會睇落完全正常。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}, start_min: '2026-08-03'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] == "start-after-history"


def test_a_bad_repo_first_commit_is_dropped_without_a_reason(page, server):
    """`repo_first_commit` 唔係人手寫嘅 —— 出一句叫人去改乜嘢都冇。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, repo_first_commit: '2026-13-01'}})")
    assert got["start"] == "2026-08-01"
    assert got["startSource"] == "observation"
    assert got["startReason"] is None


def test_the_due_gate_measures_from_the_resolved_start(page, server):
    """MAX_DAYS 個 due 閘由 start 起計 —— 起點推早咗,個閘要跟住郁。"""
    got = evaluate(page, server, f"m.resolvePlanWindow({{{FULL}, due_max: '2026-09-18'}})")
    assert got["start"] == "2026-06-16"
    assert got["due"] == "2026-09-18"
    assert got["dueReason"] is None


def test_a_plan_with_no_history_has_no_start_source(page, server):
    got = evaluate(page, server, "m.resolvePlanWindow({history: []})")
    assert got["start"] is None
    assert got["startSource"] is None
    assert got["startReason"] is None
    assert got["dueReason"] == "no-history"
```

`scripts/test_burndown_js.py` 檔尾加:

```python
EARLY_PLAN = """{
  path: 'plan.md', done: 3, total: 12, due_max: '2026-08-06',
  history_truncated: false, repo_first_commit: '2026-07-29',
  history: [
    {date: '2026-08-01', done: 0, total: 10},
    {date: '2026-08-03', done: 3, total: 12},
  ],
}"""


def test_the_window_before_the_first_observation_is_left_blank(page, server):
    """起點推早咗,但嗰段時間我哋一個數都冇量度過。Carry-back 一條平線
    等於斷言「開檔第一日就已經有 10 個 task、一個都未做」—— 作出嚟嘅線
    同真線喺畫面上分唔開。"""
    got = evaluate(page, server, f"m.burndownSeries({EARLY_PLAN}, '2026-08-04')")
    assert got["days"][:4] == ["2026-07-29", "2026-07-30", "2026-07-31", "2026-08-01"]
    assert got["remaining"][:4] == [None, None, None, 10]
    assert got["scope"][:4] == [None, None, None, 10]


def test_the_ideal_line_is_anchored_at_the_new_start(page, server):
    """理想線由起點拉到 due。起點推早咗,佢就要變平 —— 呢個正正係
    呢個改動要修嘅嘢:plan.md 開得遲會令理想線過斜。"""
    got = evaluate(page, server, f"m.burndownSeries({EARLY_PLAN}, '2026-08-04')")
    assert got["days"][-1] == "2026-08-06"
    assert got["ideal"][0] == 10          # 錨喺 history[0].total,唔係今日嘅
    assert got["ideal"][-1] == 0          # 喺 due 嗰日到零


def test_the_new_fields_reach_the_series(page, server):
    """渲染層要靠佢哋出出處同原因,唔 pass 過就永遠讀到 undefined。"""
    got = evaluate(page, server, f"m.burndownSeries({EARLY_PLAN}, '2026-08-04')")
    assert got["startSource"] == "repo"
    assert got["startReason"] is None
```

`scripts/test_timeline_js.py` 檔尾加(該檔個 helper 同 `test_burndown_js.py`
一樣叫 `evaluate(page, server, body)`,`:19-24`,已核實):

```python
SPI_PLAN = ("{done: 3, total: 12, due_max: '2026-09-01', open_tasks: [], "
            "repo_first_commit: '2026-07-01', "
            "history: [{date: '2026-08-01', done: 0, total: 10}]}")


def test_spi_measures_from_the_resolved_start(page, server):
    """SPI 個分母係計劃窗口,唔係「我哋幾時開始有記錄」。錨返第一個觀測
    會令一個做咗三個月、上星期先開 plan.md 嘅項目報一個近乎完美嘅 SPI。"""
    got = evaluate(page, server, f"m.timelineStrip({SPI_PLAN}, '2026-08-16')")
    # elapsed = (08-16 − 07-01) / (09-01 − 07-01) = 46/62 = 0.7419…
    # SPI = (3/12) / 0.7419… = 0.34;錨返 08-01 嘅話會係 0.5
    assert got["start"] == "2026-07-01"
    assert got["startSource"] == "repo"
    assert got["spi"] == 0.34


def test_the_bar_starts_at_the_resolved_start(page, server):
    got = evaluate(page, server, f"m.timelineStrip({SPI_PLAN}, '2026-08-16')")
    assert got["axisStart"] == "2026-07-01"
    assert got["barLeftPct"] == 0
```

- [ ] **Step 2: 行測試,確認佢 fail**

```bash
python -m pytest scripts/test_plan_dates_js.py scripts/test_burndown_js.py scripts/test_timeline_js.py -q
```

Expected: FAIL —— `startSource` 讀到 `undefined`;
`test_the_window_before_the_first_observation_is_left_blank` 見到
`days[0] == '2026-08-01'`。

- [ ] **Step 3: 落實作**

`docs/js/plan-dates.js`,`resolvePlanWindow()` 整個換成:

```js
/** 一個 candidate 起點用唔用得。
 *
 *  三個條件缺一不可:係一個真日曆日、唔遲過第一個觀測(遲過就同數據矛盾,
 *  要切走真嘢)、而且唔遠到爆條軸 —— `dayRange()` 個 cap 係**剪尾**嘅,
 *  剪走今日同死線,比起唔採用衰好多。 */
const usableStart = (value, firstObs) =>
  !!value && realDate(value) && value <= firstObs
    && spanDays(value, firstObs) <= MAX_DAYS;

/** 一份 plan 嘅計劃窗口:`{start, startSource, startReason, due, dueReason}`。
 *
 *  起點行三層:`plan.md` 宣告嘅 `start:` → repo 第一個 commit → 第一個
 *  plan 觀測。頭兩層都係 optional 欄位,舊 `metrics.json` 兩個都冇,自然
 *  跌到第三層 —— 即係呢個 feature 之前嘅行為。
 *
 *  `startSource` 講用咗邊層,張卡要出返俾人睇:同一條軸,由 repo 開檔拉起
 *  同由第一次改 plan.md 拉起,理想線同 SPI 嘅意思完全唔同,但畫面上一模
 *  一樣。
 *
 *  `startReason` 淨係講「人手宣告咗但用唔到」。`repo_first_commit` 唔係人手
 *  寫嘅,攞唔到或者唔啱就靜靜跌落下一層 —— 出一句叫人去改乜嘢都冇。
 *
 *  `dueReason` 唔係 null 就代表冇一個用得嘅終點,而個值就係要同用家講嘅
 *  原因。四個原因要分得開,因為要改嘅嘢完全唔同:冇 history(舊數據)、
 *  plan.md 冇寫 due:、寫咗但唔係一個畫得出嘅日期、寫咗但唔遲過起點。
 *
 *  注意 `due` 喺 'due-not-after-start' 嗰陣**仍然唔係 null** —— 佢係一個
 *  真日期,畫得落條軸,只不過拉唔出一條線。條軸要用返佢。 */
export function resolvePlanWindow(plan) {
  const history = (plan || {}).history;
  if (!Array.isArray(history) || history.length === 0) {
    return { start: null, startSource: null, startReason: null,
             due: null, dueReason: 'no-history' };
  }
  const firstObs = history[0].date;
  const declaredStart = plan.start_min || null;
  const repoStart = plan.repo_first_commit || null;

  let start = firstObs;
  let startSource = 'observation';
  if (usableStart(declaredStart, firstObs)) {
    start = declaredStart;
    startSource = 'plan';
  } else if (usableStart(repoStart, firstObs)) {
    start = repoStart;
    startSource = 'repo';
  }
  // `realDate` 要行喺日期比大細之前:`'2026-13-01' > '2026-08-01'` 係字串
  // 比較,答「係」,但佢唔係遲咗 —— 佢根本唔係一個日期。揀錯咗個 reason,
  // 張卡就會叫人去改一個唔存在嘅問題。
  const startReason = (!declaredStart || startSource === 'plan') ? null
    : !realDate(declaredStart) ? 'start-unusable'
      : declaredStart > firstObs ? 'start-after-history'
        : 'start-unusable';

  // `due_max` 淨係「shape 啱」就入到嚟(舊 metrics.json 更加乜都冇驗過),
  // 而佢係一個字串 max() 揀出嚟嘅 —— `2026-13-01` 呢類打錯嘅日期會贏晒
  // 同年所有真日期。攞唔到 timestamp(NaN)或者離譜到要畫十年以上,兩種
  // 都當「畫唔出」,唔好帶落條軸度。個 span 由**解析咗嘅**起點度起計。
  const declared = plan.due_max || null;
  const usable = !!declared && realDate(declared)
    && spanDays(start, declared) <= MAX_DAYS;
  const due = usable ? declared : null;
  // 太早嘅 due 唔算「畫唔出」:佢畫得出,只係拉唔到線 —— 所以佢喺 due
  // 有值嘅前提下先至判,同上面兩個原因分開。
  const dueReason = !declared ? 'no-due'
    : !usable ? 'due-unusable'
      : due <= start ? 'due-not-after-start'
        : null;
  return { start, startSource, startReason, due, dueReason };
}
```

`docs/js/burndown.js:14-19` 同 `:52-56`:

```js
  const { start, startSource, startReason, due, dueReason } = resolvePlanWindow(plan);
  if (!start) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, idealReason: 'no-history',
             startSource: null, startReason: null, truncated: false };
  }
```

```js
  return {
    status: history.length === 1 ? 'single-point' : 'ok',
    days, remaining, scope, ideal, todayIndex, due, idealReason,
    startSource, startReason,
    truncated: !!plan.history_truncated,
  };
```

`docs/js/timeline.js:21-26`、`:29`、`:91-93`:

```js
const EMPTY = {
  status: 'no-history', start: null, due: null, dueReason: 'no-history',
  startSource: null, startReason: null,
  axisStart: null, axisEnd: null, barLeftPct: 0, barWidthPct: 0,
  todayPct: null, markers: [], spi: null, spiReason: 'no-history',
  daysLeft: null, overdue: 0, invalidDues: 0, allDone: false,
};
```

```js
  const { start, startSource, startReason, due, dueReason } = resolvePlanWindow(plan);
```

```js
  return {
    status: 'ok', start, startSource, startReason, due, dueReason,
    axisStart, axisEnd,
    barLeftPct, barWidthPct,
```

- [ ] **Step 4: 行測試,確認全部綠**

```bash
python -m pytest scripts/test_plan_dates_js.py scripts/test_burndown_js.py scripts/test_timeline_js.py -q
```

Expected: PASS。舊 test 一個都唔應該紅 —— 佢哋全部冇 `start_min` /
`repo_first_commit`,所以行第三層。

- [ ] **Step 5: Commit**

```bash
git add docs/js/plan-dates.js docs/js/burndown.js docs/js/timeline.js scripts/test_plan_dates_js.py scripts/test_burndown_js.py scripts/test_timeline_js.py && git commit -m "feat: resolve the plan start from start:, the repo, then the first observation"
```

---

### Task 5: 卡上嘅字 —— 出處、原因、同兩句寫死咗「第一個觀測」嘅舊字

**Files:**
- Modify: `docs/js/render-burndown.js`(`:14-18` `IDEAL_CAPTION`、`:47-59` `captionFor`)
- Modify: `docs/js/render-timeline.js`(`:13-19` `NO_SPI`、`:57` `noteHTML`)
- Modify: `scripts/fixtures/metrics-fixture-burndown.json`
- Test: `scripts/test_frontend_burndown.py`、`scripts/test_frontend_timeline.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `series.startSource`、`series.startReason`(Task 4)
- Produces: 冇新 export

- [ ] **Step 1: 先搵清楚邊個現有 test 咬住舊字**

```bash
grep -rn "唔遲過第一個觀測" scripts/ docs/ README.md specs/
```

搵到嘅每一處(`specs/` 除外 —— 舊 spec 記錄當時嘅決定,唔改)都要喺 Step 4 一齊改。

- [ ] **Step 2: 寫住會 fail 嘅測試**

`scripts/fixtures/metrics-fixture-burndown.json`,`acme/alpha` 個 `plan` 入面
`due_max` 隔籬加兩行:

```json
    "start_min": null,
    "repo_first_commit": "2026-07-20",
```

(`acme/alpha` 個 `history[0].date` 係 `2026-08-01`,所以佢會行 C 層。)

`scripts/test_frontend_burndown.py` 檔尾加:

```python
def test_the_card_names_where_the_start_came_from(page, server):
    """同一條軸,由 repo 開檔拉起同由第一次改 plan.md 拉起,意思完全唔同,
    但畫面上一模一樣 —— 唔講就分唔到。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "起點:repo 第一個 commit" in dash.inner_text("#burndownCards")


def test_a_declared_start_is_named_as_such(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-06-16"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "起點:plan.md start:" in dash.inner_text("#burndownCards")


def test_an_old_metrics_json_names_the_first_plan_commit(page, server):
    """兩個 key 都冇 = 舊數據。出處要講返係第三層,唔可以扮成宣告過。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["start_min"]
    del plan["repo_first_commit"]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "起點:第一次改 plan.md" in dash.inner_text("#burndownCards")


def test_an_unusable_declared_start_says_what_to_fix(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-02-30"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    text = dash.inner_text("#burndownCards")
    assert "plan.md 個 start: 唔係一個畫得出嘅日期" in text
    assert "起點:repo 第一個 commit" in text     # 同時要講跌咗去邊


def test_a_late_declared_start_says_it_was_not_believed(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["start_min"] = "2026-08-03"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "start: 遲過第一個觀測,冇採用" in dash.inner_text("#burndownCards")


def test_the_truncated_caption_only_speaks_when_the_start_is_an_observation(page, server):
    """歷史截斷咗但起點由 repo 開檔話事嘅時候,理想線**唔係**由「現存最早
    嗰個觀測」起計 —— 照出嗰句就係講錯嘢。"""
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["history_truncated"] = True
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "已截斷" not in dash.inner_text("#burndownCards")


def test_the_truncated_caption_still_speaks_on_an_old_metrics_json(page, server):
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan["history_truncated"] = True
    del plan["start_min"]
    del plan["repo_first_commit"]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards canvas", state="attached")
    assert "已截斷" in dash.inner_text("#burndownCards")
```

- [ ] **Step 3: 行測試,確認佢 fail**

```bash
python -m pytest scripts/test_frontend_burndown.py -q
```

Expected: FAIL —— 揾唔到「起點:」嗰啲字。

- [ ] **Step 4: 落實作**

`docs/js/render-burndown.js`:

```js
/** 冇理想線嘅三個原因,逐個有自己嘅講法 —— 讀嘅人要知去改 plan.md 邊度。 */
const IDEAL_CAPTION = {
  'no-due': 'plan.md 冇 due: — 冇理想線',
  'due-unusable': 'plan.md 個 due: 唔係一個有效日期 — 冇理想線',
  'due-not-after-start': 'due: 唔遲過起點,拉唔出理想線',
};

/** 條軸個起點由邊層話事。每次都出:同一條軸,由 repo 開檔拉起同由第一次
 *  改 plan.md 拉起,理想線同 SPI 嘅意思完全唔同,但畫面上一模一樣。 */
const START_CAPTION = {
  plan: '起點:plan.md start:',
  repo: '起點:repo 第一個 commit',
  observation: '起點:第一次改 plan.md',
};

/** 宣告咗但用唔到嘅 start: —— 兩個原因要改嘅嘢唔同。冇宣告唔係一個錯,
 *  所以呢度冇第三個 key。 */
const START_REASON_CAPTION = {
  'start-unusable': 'plan.md 個 start: 唔係一個畫得出嘅日期',
  'start-after-history': 'start: 遲過第一個觀測,冇採用',
};
```

```js
function captionFor(series) {
  const bits = [];
  if (CAPTION[series.status]) bits.push(CAPTION[series.status]);
  if (START_CAPTION[series.startSource]) bits.push(START_CAPTION[series.startSource]);
  if (START_REASON_CAPTION[series.startReason]) {
    bits.push(START_REASON_CAPTION[series.startReason]);
  }
  // 以前呢度睇 `!series.due`,即係「有冇死線」。但一個宣告咗、畫唔出嘅
  // 死線(早過或者啱啱等於起點)一樣係 `due` 有值 —— 結果係冇線又冇解釋,
  // 正正係 spec §7 唔准嘅嘢。改為問 burndownSeries 本人點解冇線:條線
  // 畫唔畫同呢句講唔講,由同一個 idealReason 話事。
  if (series.idealReason) {
    bits.push(IDEAL_CAPTION[series.idealReason] || '冇理想線');
  }
  // 呢句淨係喺起點真係由「現存最早嗰個觀測」話事嗰陣先啱。起點由 start:
  // 或者 repo 開檔話事嘅時候,截斷咗嘅係中間嗰段觀測,唔係條理想線個錨。
  if (series.truncated && series.startSource === 'observation') {
    bits.push('歷史已截斷,理想線由現存最早嗰個觀測起計');
  }
  return bits.join(' · ');
}
```

`docs/js/render-timeline.js:16`:

```js
  'due-not-after-start': 'due: 唔遲過起點 — 冇 SPI',
```

`docs/js/render-timeline.js:57`(`noteHTML`):

```js
  if (s.dueReason === 'due-not-after-start') bits.push('目標日唔遲過起點,條 bar 畫到今日為止');
```

Step 1 grep 揾到嘅其餘每一處一齊改。

- [ ] **Step 5: 行測試,確認全部綠**

```bash
python -m pytest scripts/test_frontend_burndown.py scripts/test_frontend_timeline.py -q
```

Expected: PASS。

- [ ] **Step 6: README 四處要改**

`README.md` 四行寫死咗舊起點,逐行改:

| 行 | 而家 | 改做 |
|---|---|---|
| `:165` | inline 標記清單只列 `due:` / `!P0` / `#bug` | 加 `start:YYYY-MM-DD`(**只喺 heading 有效**) |
| `:176` | 「起點同每一點 \| target repo 入面 `plan.md` 嘅 commit 歷史」 | 起點同「每一點」拆開兩行:起點行三層,每一點仍然係 commit 歷史 |
| `:186` | 「**`plan.md` 開檔之前嘅嘢睇唔到。** 起點係第一個(留低嘅)commit,唔係項目真正開始嗰日。」 | 改成三層嘅講法 + 「起點早過第一個觀測嘅話,中間留白唔畫線」 |
| `:200` | 「條 bar(計劃窗口) \| `plan.md` 第一個 commit → `due:` 推斷出嚟嘅目標日」 | 左邊改成「解析咗嘅起點」 |

`:176` 嗰行改成:

```markdown
| 起點 | `plan.md` heading 嘅 `start:` → repo 第一個 commit → 第一日改過 `plan.md`。用咗邊層,卡上會寫明 |
| 每一點 | target repo 入面 `plan.md` 嘅**commit 歷史**(每日最後一個 commit,經同一個 parser 重新讀一次) |
```

`:186` 嗰行改成:

```markdown
- **起點行三層 fallback。** `plan.md` 個 heading 寫住 `start:YYYY-MM-DD` 就用佢(多過一個取最早);冇寫就用 repo 第一個 commit;連佢都攞唔到(空 repo、API 讀唔到)先至用第一日改 `plan.md` 嗰日。條軸、理想線同 SPI 三樣都跟呢個起點 —— 所以一份開檔遲過 repo 嘅 `plan.md` 唔寫 `start:` 嘅話,理想線會過斜、SPI 會偏樂觀。
- **起點早過第一個觀測嘅話,中間嗰段留白。** 嗰段時間我哋一個數都冇量度過,拉一條平線過去就等於話你聽「開檔第一日就已經有 N 個 task、一個都未做」。
- **`start:` 寫錯咗唔會靜靜哋跌走。** 唔係一個畫得出嘅日期(唔存在,或者離遠到爆條軸),又或者遲過第一個觀測(即係同 git 記錄矛盾),兩種都唔採用,跌落下一層,而卡上會講明係邊一種。
```

- [ ] **Step 7: 全套測試**

```bash
python -m pytest scripts/ -q
```

Expected: **369 + 新增數** passed,`0 failed`。呢個要行足 12 分鐘。

- [ ] **Step 8: Commit**

```bash
git add docs/js/render-burndown.js docs/js/render-timeline.js scripts/test_frontend_burndown.py scripts/test_frontend_timeline.py scripts/fixtures/metrics-fixture-burndown.json README.md && git commit -m "feat: name the burndown axis start source on the card"
```

---

## 落手之前要知

- **老 repo 會即刻變紅。** 冇 `start:` 嘅 repo 全部行 C 層,條軸可能由一兩年前
  拉起,SPI 插到近 0。呢個係設計 §9 已經接受咗嘅後果,唔係 regression。
- **`config.toml` 今日得兩個 repo 設咗 `plan_file`**,所以真實影響面係兩張卡,
  收集端多四個 REST request。
- **全套測試行足 12 分鐘**(Playwright)。所以每個 task 只行自己嗰幾個檔,
  Task 5 Step 7 先至行全套。
