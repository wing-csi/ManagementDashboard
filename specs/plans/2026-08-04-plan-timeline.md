# Plan Timeline Strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-repo plan timeline strip — a schedule header (SPI · days left · overdue count) above a horizontal axis carrying the plan window and one marker per open task due date — into the burndown card that already exists for every repo with a `plan_file`.

**Architecture:** Everything the strip needs is already in `metrics.json`; there is no collector work. The date rules that decide whether `due_max` is usable currently live private inside `docs/js/burndown.js` and took three fix commits to get right, so Task 1 lifts them into `docs/js/plan-dates.js` unchanged and points the burndown at it. Tasks 2–3 then build shaping (`timeline.js`, pure, DOM-free) and rendering (`render-timeline.js`, an HTML-string function) on top of that shared base, and `render-burndown.js` splices the string into the card it already builds.

**Tech Stack:** Vanilla ES modules, no build step. CSS percentage positioning — **no Chart.js** for the strip (Chart.js 4 has no Gantt/range type). pytest + pytest-playwright for tests, Python 3.11+ stdlib.

**Source spec:** [`specs/2026-08-04-plan-timeline-design.md`](../2026-08-04-plan-timeline-design.md)

## Global Constraints

- **No new dependencies.** No `package.json`, no build step, no new CDN `<script>` tags.
- **No collector change, no new `config.toml` key, no new `metrics.json` field.** The strip reads only fields that ship today.
- **`docs/js/burndown.js` must stay behaviour-identical** through Task 1. `scripts/test_burndown_js.py` is the regression guard and must pass **without being edited**. If a burndown test needs changing, the extraction is wrong — stop and re-read the original.
- **User-facing strings are Cantonese**, matching every existing card in `docs/js/`.
- **The strip does not follow the window selector** (30/60/90/180). Nothing in the new code may read `state.windowDays`.
- **Every absence explains itself.** No line, marker, or number may be omitted without the card saying why — spec §8. The same condition must gate both the drawing and the caption, so the two can never drift apart.
- **The full suite must stay green:** `python -m pytest scripts/ -q` — **330 passed** today. Every task adds; none subtracts.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/js/plan-dates.js` (create) | Shared plan-date rules: `DAY`, `MAX_DAYS`, `toMs`, `toISO`, `spanDays`, `realDate`, `dayRange`, `resolvePlanWindow`. No DOM, no other imports. |
| `docs/js/burndown.js` (modify) | Import the above instead of defining it. Behaviour unchanged. |
| `docs/js/timeline.js` (create) | `timelineStrip(plan, today)` — pure shaping, no DOM. |
| `docs/js/render-timeline.js` (create) | `timelineHTML(plan, today) -> string`. Builds markup only; never touches the DOM. |
| `docs/js/render-burndown.js` (modify) | Splice that string into the card it already builds. |
| `docs/css/dashboard.css` (modify) | `.tl-*` classes, beside the existing `.burndown-card` block at `:431-438`. |
| `scripts/test_plan_dates_js.py` (create) | Unit tests for `resolvePlanWindow` — the one genuinely new function in Task 1. |
| `scripts/test_timeline_js.py` (create) | Unit tests for `timelineStrip`. |
| `scripts/test_frontend_timeline.py` (create) | Playwright rendering tests. |
| `scripts/fixtures/metrics-fixture-burndown.json` (modify) | Give `open_tasks` real dues so the strip has markers. |
| `README.md` (modify) | Document the strip, its inputs, and its limits. |

Dependencies run one way: `plan-dates` ← `timeline` ← `render-timeline` ← `render-burndown`. Chart lifecycle is untouched.

---

### Task 1: Extract `plan-dates.js`

A pure lift-and-shift plus one new composed function. `realDate`, `spanDays`, `MAX_DAYS` and the `due_max` validation took `04b57d2`, `514608b` and `9be6968` to get right; the timeline needs identical semantics, and two independently-evolving copies will eventually disagree about the same `metrics.json`.

**Files:**
- Create: `docs/js/plan-dates.js`
- Modify: `docs/js/burndown.js:1-105` (whole file)
- Test: `scripts/test_plan_dates_js.py` (create)

**Interfaces:**
- Consumes: nothing (first task)
- Produces, all from `docs/js/plan-dates.js`:
  - `DAY: number` (864e5), `MAX_DAYS: number` (3653)
  - `toMs(s: string) -> number`, `toISO(ms: number) -> string`
  - `spanDays(start: string, end: string) -> number` — inclusive day count
  - `realDate(s: string) -> boolean`
  - `dayRange(start: string, end: string) -> string[]`
  - `resolvePlanWindow(plan: object) -> {start: string|null, due: string|null, dueReason: string|null}` where `dueReason` ∈ `null | 'no-history' | 'no-due' | 'due-unusable' | 'due-not-after-start'`

> **Signature note:** the spec wrote `resolvePlanWindow(plan, today)`. `today` is not used — the window is start-to-due, and today only matters to the axis and SPI, both of which are Task 2's job. Dropping the unused parameter, deliberately.

> **Equivalence that makes this safe:** the burndown currently derives `'due-not-after-start'` from `dueIndex <= 0`, where `dueIndex = days.indexOf(due)` and `days` begins at `start`. `indexOf` returns `0` when `due === start` and `-1` when `due < start`, so `dueIndex <= 0` is exactly `due <= start` on ISO strings. `due` is already capped by `spanDays(start, due) <= MAX_DAYS`, so it can never fall outside the range that `dayRange` truncates. The new form is identical, not merely similar.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_plan_dates_js.py`:

```python
"""Unit tests for docs/js/plan-dates.js, executed in a real browser.

Same approach as test_burndown_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

What is under test is the single question both the burndown and the timeline
have to answer the same way: 「呢份 plan 有冇一個畫得出嘅終點,冇嘅話係
點解」. Two copies of this rule drifting apart is the whole reason it moved
into its own module.

Run:  python -m pytest scripts/test_plan_dates_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="plan-dates.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/plan-dates.js'); "
        f"return ({body}); }}"
    )


HIST = "history: [{date: '2026-08-01', done: 0, total: 10}]"


def test_a_plan_with_a_usable_due_has_no_reason(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-09-18'}})")
    assert got == {"start": "2026-08-01", "due": "2026-09-18", "dueReason": None}


def test_no_history_is_its_own_reason(page, server):
    """舊 metrics.json 冇 history — 同「有 history 但冇 due:」要分得開。"""
    got = evaluate(page, server, "m.resolvePlanWindow({due_max: '2026-09-18'})")
    assert got["start"] is None
    assert got["dueReason"] == "no-history"


def test_a_plan_without_any_due_says_no_due(page, server):
    got = evaluate(page, server, f"m.resolvePlanWindow({{{HIST}}})")
    assert got["due"] is None
    assert got["dueReason"] == "no-due"


def test_a_calendar_invalid_due_is_unusable_not_absent(page, server):
    """2026-02-30 唔會出 NaN — JS 靜靜哋當佢 3 月 2 日。要分得出
    「冇寫」同「寫錯咗」,因為兩者要改嘅嘢唔同。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-02-30'}})")
    assert got["due"] is None
    assert got["dueReason"] == "due-unusable"


def test_an_absurd_year_is_unusable(page, server):
    """due:2926-09-18 打錯年份 — 一放落條軸就係三十幾萬個日期。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2926-09-18'}})")
    assert got["dueReason"] == "due-unusable"


def test_a_due_on_the_start_day_cannot_carry_a_line(page, server):
    """啱啱等於起點:個日期畫得出,但拉唔出一條線 — 第三個原因。"""
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-08-01'}})")
    assert got["due"] == "2026-08-01"
    assert got["dueReason"] == "due-not-after-start"


def test_a_due_before_the_start_is_the_same_reason(page, server):
    got = evaluate(page, server,
                   f"m.resolvePlanWindow({{{HIST}, due_max: '2026-07-01'}})")
    assert got["dueReason"] == "due-not-after-start"


def test_real_date_rejects_the_shapes_that_parse_but_do_not_exist(page, server):
    got = evaluate(page, server,
                   "[m.realDate('2026-08-04'), m.realDate('2026-02-30'), "
                   "m.realDate('2026-13-01')]")
    assert got == [True, False, False]


def test_span_days_is_inclusive(page, server):
    got = evaluate(page, server, "m.spanDays('2026-08-01', '2026-08-04')")
    assert got == 4
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_plan_dates_js.py -v
```

Expected: all 9 FAIL — the dynamic `import('/js/plan-dates.js')` rejects because the file does not exist.

- [ ] **Step 3: Create `docs/js/plan-dates.js`**

Every comment below is carried over verbatim from `burndown.js`; they record why each guard exists and must not be summarised away.

```js
/** Plan 日期嘅共用規矩 —— burndown 同 timeline 兩張圖都要一模一樣嘅答案。
 *
 *  呢啲嘢本來係 burndown.js 嘅私有嘢,用咗三個修正 commit 先至啱
 *  (04b57d2 日曆驗證、514608b 冇線要講點解、9be6968 commit list 分頁)。
 *  兩份各自演化嘅日期驗證,遲早會喺同一個 metrics.json 上面畫出兩個唔同
 *  嘅結論,而兩個都會睇落好合理。
 */

export const DAY = 864e5;

/** 一條軸最多畫幾多日(約十年)。
 *
 *  `plan.md` 係喺目標 repo 度人手改嘅,collector 由今次起會驗日曆,但舊
 *  `metrics.json` 入面嘅 `due_max` 未驗過。一個打錯咗嘅年份(`due:2926-09-18`)
 *  會叫 dayRange() 生 328,767 個日期,再乘三條 dataset 交去 Chart.js ——
 *  main thread 一卡就唔止呢張卡死,成個 dashboard 一齊死。 */
export const MAX_DAYS = 3653;

export const toMs = (s) => new Date(s + 'T00:00:00Z').getTime();
export const toISO = (ms) => new Date(ms).toISOString().slice(0, 10);

/** start..end(包頭包尾)有幾多日;任何一邊唔係真日期就出 NaN。 */
export const spanDays = (start, end) => Math.floor((toMs(end) - toMs(start)) / DAY) + 1;

/** 真係存在嘅日曆日?
 *
 *  唔淨止係 NaN check:`2026-13-01` 同 `2026-08-32` 出 NaN,但 `2026-02-30`
 *  唔會 —— JS 會靜靜哋當佢係 3 月 2 日。咁樣喺條軸上面就永遠 indexOf 唔到,
 *  變成一個「冇線,而且講錯咗理由」嘅 card。Round-trip 返轉頭一定要係
 *  原本嗰串字,兩種都一次過擋晒。 */
export const realDate = (s) => {
  const ms = toMs(s);
  return Number.isFinite(ms) && toISO(ms) === s;
};

/** start..end(包頭包尾)每一日嘅 ISO 日期。
 *
 *  封頂 MAX_DAYS 個係最後一道 allocation 閘(例如一個 clock 壞咗嘅 commit
 *  日期);正常範圍同呢個上限差幾個數量級,撞唔到。 */
export function dayRange(start, end) {
  const out = [];
  for (let ms = toMs(start); ms <= toMs(end) && out.length < MAX_DAYS; ms += DAY) {
    out.push(toISO(ms));
  }
  return out;
}

/** 一份 plan 嘅計劃窗口:`{start, due, dueReason}`。
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
    return { start: null, due: null, dueReason: 'no-history' };
  }
  const start = history[0].date;
  // `due_max` 淨係「shape 啱」就入到嚟(舊 metrics.json 更加乜都冇驗過),
  // 而佢係一個字串 max() 揀出嚟嘅 —— `2026-13-01` 呢類打錯嘅日期會贏晒
  // 同年所有真日期。攞唔到 timestamp(NaN)或者離譜到要畫十年以上,兩種
  // 都當「畫唔出」,唔好帶落條軸度。
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
  return { start, due, dueReason };
}
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
python -m pytest scripts/test_plan_dates_js.py -v
```

Expected: 9 PASS.

- [ ] **Step 5: Point `burndown.js` at the shared module**

Replace `docs/js/burndown.js` lines 1–68 (the header comment through `const days = dayRange(start, end);`) with the following. Everything from `const byDate = ...` to the end of the file is **unchanged** — do not retype it.

```js
/** 項目 burndown 嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  收集端只出「plan.md 真係改過嗰啲日」嘅觀測(見 scripts/plan_history.py)。
 *  中間嗰啲平坦日子喺呢度 carry-forward 補返:焗入 JSON 嘅話,一條階梯函數
 *  同真正嘅每日取樣就完全分唔開。
 *
 *  日期嗰套規矩(邊個 due_max 用得、點解用唔得)住喺 plan-dates.js,同
 *  timeline 條線共用 —— 兩張圖一定要對同一份 plan 講同一個答案。
 */

import { dayRange, resolvePlanWindow } from './plan-dates.js';

export function burndownSeries(plan, todayStr) {
  const { start, due, dueReason } = resolvePlanWindow(plan);
  if (!start) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, idealReason: 'no-history',
             truncated: false };
  }

  const history = plan.history;
  const lastObs = history[history.length - 1].date;
  // 死線過咗都要見到今日,否則個圖會喺死線度斷;ISO 日期直接字串比大細。
  const end = [due || lastObs, lastObs, todayStr].sort().pop();
  const days = dayRange(start, end);
```

Then, further down, replace the `idealReason` block (the `const idealReason = !declared ? ...` statement and the comment above it) with:

```js
  // 冇理想線就一定要講得出點解(spec §7)。四個原因而家由 resolvePlanWindow
  // 判,burndown 同 timeline 共用同一套字 —— 兩張卡對住同一份 plan,唔會
  // 一張話「冇寫 due:」另一張話「寫錯咗」。
  const idealReason = dueReason;
```

`const dueIndex = due ? days.indexOf(due) : -1;` stays exactly where it is — the `ideal` map below still needs it to place the zero point.

- [ ] **Step 6: Run the burndown regression guard, unedited**

```bash
python -m pytest scripts/test_burndown_js.py scripts/test_plan_dates_js.py -v
```

Expected: every burndown test PASSES **with no edits to `test_burndown_js.py`**. If any fails, the extraction changed behaviour — revert and re-read `burndown.js` at `9be6968` rather than adjusting the test.

- [ ] **Step 7: Run the whole suite**

```bash
python -m pytest scripts/ -q
```

Expected: **339 passed** (330 baseline + 9 new).

- [ ] **Step 8: Commit**

```bash
git add docs/js/plan-dates.js docs/js/burndown.js scripts/test_plan_dates_js.py
git commit -m "refactor: share the plan-date rules between burndown and timeline"
```

---

### Task 2: `timeline.js` — plan and tasks to a strip

Pure shaping, no DOM, testable the way `burndown.js` and `aggregate.js` are.

**Files:**
- Create: `docs/js/timeline.js`
- Test: `scripts/test_timeline_js.py` (create)

**Interfaces:**
- Consumes: `DAY`, `MAX_DAYS`, `toMs`, `toISO`, `spanDays`, `realDate`, `resolvePlanWindow` from `./plan-dates.js` (Task 1)
- Produces: `timelineStrip(plan: object, todayStr: string) -> object` with exactly these keys:
  - `status`: `'ok' | 'no-history'`
  - `start`, `due`: `string|null` — the declared plan window
  - `dueReason`: `string|null` — passed through from `resolvePlanWindow`
  - `axisStart`, `axisEnd`: `string|null` — what the axis actually spans
  - `barLeftPct`, `barWidthPct`: `number` — the window bar, as percentages of the axis
  - `todayPct`: `number|null` — null when today falls before the axis
  - `markers`: `Array<{date, leftPct, urgency, daysFromToday, count, tasks: Array<{title, priority, bug}>}>`, ascending by date; `urgency` ∈ `'overdue' | 'soon7' | 'soon14' | 'later'`
  - `spi`: `number|null` — two decimal places
  - `spiReason`: `string|null` — `dueReason`, or `'not-started'`, or `'no-tasks'`
  - `daysLeft`: `number|null`
  - `overdue`: `number` — count of tasks, not markers
  - `invalidDues`: `number`
  - `allDone`: `boolean`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_timeline_js.py`:

```python
"""Unit tests for docs/js/timeline.js, executed in a real browser.

Same approach as test_burndown_js.py. The two things most likely to go wrong
silently are covered hardest: a marker falling outside the axis (drawn
nowhere, explained nowhere), and SPI dividing by a zero-length elapsed window
(rendering Infinity or NaN as if it were a measurement).

Run:  python -m pytest scripts/test_timeline_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="timeline.js unit tests need pytest-playwright")


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/timeline.js'); "
        f"return ({body}); }}"
    )


PLAN = """{
  path: 'plan.md', done: 3, total: 12, due_max: '2026-08-06',
  history: [
    {date: '2026-08-01', done: 0, total: 10},
    {date: '2026-08-03', done: 3, total: 12},
  ],
  open_tasks: [
    {title: 'P-01', due: '2026-08-01', priority: 'P1', bug: true},
    {title: 'P-02', due: '2026-08-01', priority: 'P2', bug: false},
    {title: 'P-03', due: '2026-08-06', priority: 'P1', bug: false},
    {title: 'P-04', due: '2026-08-20', priority: 'P2', bug: false},
  ],
}"""


def test_the_axis_stretches_past_due_max_to_cover_a_later_task(page, server):
    """一個遲過 due_max 嘅 task 一樣係真嘢。軸唔撐開,嗰粒就跌出畫面 ——
    冇畫,又冇講,正正係 514608b 修過嗰種錯。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["axisStart"] == "2026-08-01"
    assert got["axisEnd"] == "2026-08-20"


def test_the_axis_stretches_back_for_a_task_due_before_the_plan_started(page, server):
    plan = PLAN.replace("{title: 'P-04', due: '2026-08-20'",
                        "{title: 'P-04', due: '2026-07-20'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["axisStart"] == "2026-07-20"


def test_tasks_sharing_a_date_become_one_marker(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    first = got["markers"][0]
    assert first["date"] == "2026-08-01"
    assert first["count"] == 2
    assert [t["title"] for t in first["tasks"]] == ["P-01", "P-02"]


def test_overdue_counts_tasks_not_markers(page, server):
    """兩個 task 迫喺同一日,係兩個過期,唔係一個。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["overdue"] == 2


def test_markers_are_classified_by_distance_from_today(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert [m["urgency"] for m in got["markers"]] == ["overdue", "soon7", "later"]


def test_the_bar_spans_the_declared_window_not_the_axis(page, server):
    """條 bar 係「計劃咗幾耐」,條軸係「要畫幾闊」。撈埋一齊嘅話,
    一個遲 task 就會令個項目睇落計劃到 8 月 20 號。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["barLeftPct"] == 0
    # 08-01..08-06 係 20 日軸(08-01..08-20)入面嘅頭 6 日
    assert round(got["barWidthPct"]) == 26


def test_spi_divides_progress_by_elapsed_time(page, server):
    """3/12 做完,而 08-01→08-06 走咗 3/5。0.25 / 0.6 = 0.42。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["spi"] == 0.42
    assert got["spiReason"] is None


def test_spi_is_absent_before_the_plan_starts(page, server):
    """今日 == 起點:elapsed 係 0,除唔到。要出「未開始」,唔可以出 Infinity。"""
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-01')")
    assert got["spi"] is None
    assert got["spiReason"] == "not-started"


def test_spi_is_absent_when_the_due_is_unusable(page, server):
    plan = PLAN.replace("due_max: '2026-08-06'", "due_max: '2026-02-30'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["spi"] is None
    assert got["spiReason"] == "due-unusable"
    assert got["daysLeft"] is None


def test_a_zero_task_plan_is_not_behind_schedule(page, server):
    """0/0 係 NaN,而 NaN 輸晒所有比較,最後會靜靜哋顯示做「嚴重落後」。
    冇 task 唔係落後。"""
    plan = PLAN.replace("done: 3, total: 12", "done: 0, total: 0")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["spi"] is None
    assert got["spiReason"] == "no-tasks"


def test_days_left_counts_from_today_to_the_due(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-04')")
    assert got["daysLeft"] == 2


def test_days_left_goes_negative_once_the_due_has_passed(page, server):
    got = evaluate(page, server, f"m.timelineStrip({PLAN}, '2026-08-10')")
    assert got["daysLeft"] == -4


def test_a_calendar_invalid_task_due_is_dropped_and_counted(page, server):
    """靜靜哋掉咗會令「過期」個數虛低 —— 數低咗先講得出。"""
    plan = PLAN.replace("{title: 'P-04', due: '2026-08-20'",
                        "{title: 'P-04', due: '2026-02-30'")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["invalidDues"] == 1
    assert all(mk["date"] != "2026-02-30" for mk in got["markers"])


def test_a_plan_with_no_dated_tasks_still_has_a_bar(page, server):
    plan = PLAN.replace(PLAN[PLAN.index("open_tasks"):PLAN.rindex("],") + 2],
                        "open_tasks: []")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["markers"] == []
    assert got["axisEnd"] == "2026-08-06"


def test_all_tasks_ticked_is_flagged_separately(page, server):
    """「冇嘢剩低」同「冇寫 due:」兩個都係零粒 marker,但意思啱啱相反。"""
    plan = PLAN.replace("done: 3, total: 12", "done: 12, total: 12")
    got = evaluate(page, server, f"m.timelineStrip({plan}, '2026-08-04')")
    assert got["allDone"] is True


def test_no_history_reports_no_history(page, server):
    got = evaluate(page, server,
                   "m.timelineStrip({path: 'plan.md', done: 1, total: 2}, '2026-08-04')")
    assert got["status"] == "no-history"
    assert got["markers"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_timeline_js.py -v
```

Expected: all 16 FAIL — `import('/js/timeline.js')` rejects, the file does not exist.

- [ ] **Step 3: Implement**

Create `docs/js/timeline.js`:

```js
/** Plan timeline 條嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  Marker 來自 `plan.open_tasks[]`,即係**未打勾**嗰啲。做完嘅 task 唔會
 *  留低痕跡,所以呢條線讀做「仲有乜嘢喺前面」,唔係「成個項目嘅里程碑」。
 *  卡上要寫明呢點:task 一路做完條線一路變疏,同「一切順利」喺畫面上
 *  睇落一模一樣。
 */

import {
  DAY, MAX_DAYS, toMs, toISO, spanDays, realDate, resolvePlanWindow,
} from './plan-dates.js';

/** 急切度淨係睇日期 —— 同「項目」分頁 milestone 行嘅 late 邏輯一致。 */
function urgencyOf(daysFromToday) {
  if (daysFromToday < 0) return 'overdue';
  if (daysFromToday <= 7) return 'soon7';
  if (daysFromToday <= 14) return 'soon14';
  return 'later';
}

const EMPTY = {
  status: 'no-history', start: null, due: null, dueReason: 'no-history',
  axisStart: null, axisEnd: null, barLeftPct: 0, barWidthPct: 0,
  todayPct: null, markers: [], spi: null, spiReason: 'no-history',
  daysLeft: null, overdue: 0, invalidDues: 0, allDone: false,
};

export function timelineStrip(plan, todayStr) {
  const { start, due, dueReason } = resolvePlanWindow(plan);
  if (!start) return { ...EMPTY };

  const open = (plan.open_tasks || []).filter((t) => t && t.due);
  const valid = open.filter((t) => realDate(t.due));
  const invalidDues = open.length - valid.length;

  // 條軸要罩得住每一粒真 marker 同今日。一粒跌咗出畫面,就係「冇畫又冇
  // 講」;今日跌咗出去,「過唔過期」就冇咗參照點。
  const dates = valid.map((t) => t.due);
  const axisStart = [start, ...dates].sort()[0];
  let axisEnd = [due || start, ...dates, todayStr].sort().pop();
  // 同 dayRange 一樣嘅 allocation 閘:一個壞日期唔可以令個 axis 拉到十年外。
  if (spanDays(axisStart, axisEnd) > MAX_DAYS) {
    axisEnd = toISO(toMs(axisStart) + (MAX_DAYS - 1) * DAY);
  }

  const span = spanDays(axisStart, axisEnd);
  const pct = (d) => (span <= 1 ? 0 : ((toMs(d) - toMs(axisStart)) / DAY) / (span - 1) * 100);

  const todayMs = toMs(todayStr);
  const byDate = new Map();
  for (const t of valid) {
    if (!byDate.has(t.due)) byDate.set(t.due, []);
    byDate.get(t.due).push({
      title: t.title || '', priority: t.priority || null, bug: !!t.bug,
    });
  }
  const markers = [...byDate.keys()].sort().map((date) => {
    const tasks = byDate.get(date);
    const daysFromToday = Math.round((toMs(date) - todayMs) / DAY);
    return {
      date, leftPct: pct(date), urgency: urgencyOf(daysFromToday),
      daysFromToday, count: tasks.length, tasks,
    };
  });
  const overdue = markers
    .filter((mk) => mk.urgency === 'overdue')
    .reduce((n, mk) => n + mk.count, 0);

  // 條 bar 係「計劃咗幾耐」。冇一個用得嘅終點就冇計劃窗口 —— 改為畫到
  // 今日,讀做「行咗幾耐」。兩者喺畫面上一樣咁闊,所以 caption 一定要
  // 講返係邊一種(render-timeline.js)。
  const barEnd = dueReason ? todayStr : due;
  const barLeftPct = pct(start);
  const barWidthPct = Math.max(0, pct(barEnd) - barLeftPct);

  const total = plan.total || 0;
  const done = plan.done || 0;
  let spi = null;
  let spiReason = null;
  if (dueReason) {
    spiReason = dueReason;
  } else if (total <= 0) {
    // 0/0 係 NaN,而 NaN 輸晒所有 band 比較,最後靜靜哋顯示做「嚴重落後」。
    spiReason = 'no-tasks';
  } else {
    const elapsed = (todayMs - toMs(start)) / (toMs(due) - toMs(start));
    if (!(elapsed > 0)) spiReason = 'not-started';
    else spi = +((done / total) / elapsed).toFixed(2);
  }

  return {
    status: 'ok', start, due, dueReason, axisStart, axisEnd,
    barLeftPct, barWidthPct,
    todayPct: todayStr < axisStart ? null : pct(todayStr),
    markers, spi, spiReason,
    // 冇終點就冇「剩幾多」—— 唔可以攞今日或者最遲嗰粒 marker 嚟頂替。
    daysLeft: dueReason ? null : Math.round((toMs(due) - todayMs) / DAY),
    overdue, invalidDues,
    allDone: total > 0 && done >= total,
  };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_timeline_js.py -v
```

Expected: 16 PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/js/timeline.js scripts/test_timeline_js.py
git commit -m "feat: shape a plan into a timeline strip with SPI and due markers"
```

---

### Task 3: Render the strip into the burndown card

**Files:**
- Create: `docs/js/render-timeline.js`
- Modify: `docs/js/render-burndown.js:1-2` (imports) and `:78-84` (card markup)
- Modify: `docs/css/dashboard.css` — append after the `.burndown-card` block at `:431-438`
- Modify: `scripts/fixtures/metrics-fixture-burndown.json`
- Test: `scripts/test_frontend_timeline.py` (create)

**Interfaces:**
- Consumes: `timelineStrip(plan, todayStr)` (Task 2); `esc` from `./data.js`
- Produces: `timelineHTML(plan: object, todayStr: string) -> string`, exported from `docs/js/render-timeline.js`. Returns `''` when `status === 'no-history'`. Never touches the DOM.

- [ ] **Step 1: Extend the fixture**

In `scripts/fixtures/metrics-fixture-burndown.json`, replace `repo_meta["acme/alpha"].plan.open_tasks` (currently `[]`) with:

```json
[
  {"title": "P-01 過咗期嘅嘢", "due": "2026-08-01", "priority": "P1", "bug": true, "section": "Phase 2"},
  {"title": "P-02 同日另一件", "due": "2026-08-01", "priority": "P2", "bug": false, "section": "Phase 2"},
  {"title": "P-03 就快到期", "due": "2026-08-06", "priority": "P1", "bug": false, "section": "Phase 2"},
  {"title": "P-04 遲過目標日", "due": "2026-08-20", "priority": "P2", "bug": false, "section": "Phase 2"}
]
```

Leave every other key alone — `generated_at` stays `"2026-08-04T00:00:00+00:00"`, so today is deterministic, and `test_frontend_burndown.py` keeps passing against the same `history` and `due_max`.

- [ ] **Step 2: Write the failing tests**

Create `scripts/test_frontend_timeline.py`:

```python
"""Plan timeline 條嘅渲染守則。

同 burndown 卡一樣嘅規矩:冇畫嘅嘢一定要講得出點解。條線最容易靜靜哋
出錯嘅地方係空狀態 —— 每一個都要有自己嘅講法,唔可以共用一句,亦唔可以
留一格白。

Run:  python -m pytest scripts/test_frontend_timeline.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="timeline rendering tests need pytest-playwright")

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


def test_the_strip_renders_one_marker_per_distinct_due(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark",
                                     "els => els.length") == 3


def test_overdue_markers_are_marked_overdue(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark.tl-overdue",
                                     "els => els.length") == 1


def test_the_header_reports_spi_days_left_and_overdue_count(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-head", state="attached")
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0.42" in head      # 3/12 done ÷ 3/5 elapsed
    assert "嚴重落後" in head
    assert "剩 2 日" in head
    assert "2 個 task 過咗期" in head


def test_a_marker_carries_its_tasks_in_the_tooltip(page, server):
    """兩個 task 迫埋同一日 — tooltip 要列晒,唔可以淨係講一個。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-mark", state="attached")
    tip = dash.eval_on_selector("#burndownCards .tl-mark",
                                "el => el.getAttribute('title')")
    assert "P-01" in tip and "P-02" in tip
    assert "P1" in tip


def test_today_is_marked_on_the_strip(page, server):
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl-today", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl-today",
                                     "els => els.length") == 1


def test_the_strip_always_says_it_only_shows_unfinished_work(page, server):
    """條線只畫未打勾嘅 task。唔講嘅話,做完嘢令條線變疏會被讀成「順利」。"""
    _serve(page, _load())
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "未做" in dash.inner_text("#burndownCards .tl")


def test_an_unusable_due_says_so_and_shows_no_spi(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["due_max"] = "2026-02-30"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "唔係一個有效日期" in text
    # 唔可以斷言「冇 SPI 呢三個字」—— 解釋嗰句本身就有「冇 SPI」。要斷言嘅
    # 係冇一個 SPI **數字**,亦冇任何一個 band 判斷。
    head = dash.inner_text("#burndownCards .tl-head")
    assert "SPI 0." not in head
    assert not any(band in head for band in ("追得上", "落後", "嚴重落後"))


def test_a_plan_with_no_task_dues_says_so(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["open_tasks"] = []
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "冇寫 due:" in dash.inner_text("#burndownCards .tl")
    assert dash.eval_on_selector_all("#burndownCards .tl-mark",
                                     "els => els.length") == 0


def test_a_finished_plan_says_nothing_is_left_not_no_dates(page, server):
    """「冇嘢剩低」同「冇寫 due:」兩個都係零粒 marker,唔可以共用一句。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    plan["open_tasks"] = []
    plan["done"] = plan["total"]
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    text = dash.inner_text("#burndownCards .tl")
    assert "冇嘢剩低" in text
    assert "冇寫 due:" not in text


def test_invalid_task_dues_are_counted_in_the_note(page, server):
    data = _load()
    data["repo_meta"]["acme/alpha"]["plan"]["open_tasks"].append(
        {"title": "P-99 壞日期", "due": "2026-02-30", "priority": "P2",
         "bug": False, "section": "Phase 2"})
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .tl", state="attached")
    assert "1 個" in dash.inner_text("#burndownCards .tl")


def test_a_failed_history_fetch_draws_no_strip_at_all(page, server):
    """Burndown 已經出咗聲,條線唔好再嘈一次 —— 亦唔可以扮有數據。"""
    data = _load()
    plan = data["repo_meta"]["acme/alpha"]["plan"]
    del plan["history"]
    plan["history_error"] = "攞唔到 plan.md 嘅 commit 歷史"
    _serve(page, data)
    dash = _open(page, server)
    dash.wait_for_selector("#burndownCards .burndown-card", state="attached")
    assert dash.eval_on_selector_all("#burndownCards .tl", "els => els.length") == 0


def test_old_metrics_without_plan_history_render_no_strip(page, server):
    data = _load()
    for meta in data["repo_meta"].values():
        meta.pop("plan", None)
    _serve(page, data)
    dash = _open(page, server)
    assert dash.eval_on_selector("#burndownCards", "el => el.children.length") == 0
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_frontend_timeline.py -v
```

Expected: FAIL — no `.tl` element exists.

- [ ] **Step 4: Create `docs/js/render-timeline.js`**

```js
import { esc } from './data.js';
import { timelineStrip } from './timeline.js';

/** SPI 三個 band。同 burndown 一樣,顏色由 CSS class 話事,唔喺 JS 度寫死。 */
function spiBand(spi) {
  if (spi >= 1) return { cls: 'tl-ok', text: '追得上' };
  if (spi >= 0.8) return { cls: 'tl-warn', text: '落後' };
  return { cls: 'tl-bad', text: '嚴重落後' };
}

/** 冇 SPI 嘅五個原因,逐個有自己嘅講法 —— 頭三個同 burndown 個
 *  IDEAL_CAPTION 用同一套字,因為背後係同一個 dueReason。 */
const NO_SPI = {
  'no-due': 'plan.md 冇 due: — 冇 SPI',
  'due-unusable': 'plan.md 個 due: 唔係一個有效日期 — 冇 SPI',
  'due-not-after-start': 'due: 唔遲過第一個觀測 — 冇 SPI',
  'not-started': '未開始',
  'no-tasks': 'plan.md 冇 task',
};

function headHTML(s) {
  const bits = [];
  if (s.spi != null) {
    const band = spiBand(s.spi);
    bits.push(`<span class="${band.cls}">SPI ${s.spi} · ${band.text}</span>`);
  } else {
    bits.push(`<span class="tl-muted">${esc(NO_SPI[s.spiReason] || '冇 SPI')}</span>`);
  }
  if (s.daysLeft != null) {
    bits.push(s.daysLeft >= 0
      ? `剩 ${s.daysLeft} 日`
      : `<span class="tl-bad">遲咗 ${Math.abs(s.daysLeft)} 日</span>`);
  }
  if (s.overdue > 0) bits.push(`<span class="tl-bad">${s.overdue} 個 task 過咗期</span>`);
  return `<div class="tl-head">${bits.join(' · ')}</div>`;
}

function markerHTML(mk) {
  const lines = mk.tasks.map((t) => {
    const tags = [t.priority, t.bug ? '#bug' : null].filter(Boolean).join(' ');
    return tags ? `${t.title} (${tags})` : t.title;
  });
  const tip = `${mk.date}\n${lines.join('\n')}`;
  const label = mk.count > 1 ? String(mk.count) : '';
  return `<span class="tl-mark tl-${mk.urgency}" style="left:${mk.leftPct.toFixed(2)}%"`
    + ` title="${esc(tip)}">${esc(label)}</span>`;
}

/** 條線一定要講嘅嘢。第一句每次都出:條線只畫未打勾嘅 task,唔講嘅話
 *  「做完嘢令條線變疏」同「一切順利」喺畫面上分唔開。 */
function noteHTML(s) {
  const bits = ['條線只畫未做嘅 task'];
  if (s.allDone) bits.push('冇嘢剩低');
  else if (!s.markers.length) bits.push('plan.md 啲 task 冇寫 due:');
  if (s.dueReason === 'no-due') bits.push('冇目標日,條 bar 畫到今日為止');
  if (s.dueReason === 'due-unusable') bits.push('目標日唔係一個有效日期,條 bar 畫到今日為止');
  if (s.dueReason === 'due-not-after-start') bits.push('目標日唔遲過起點,條 bar 畫到今日為止');
  if (s.invalidDues > 0) bits.push(`${s.invalidDues} 個 task 嘅 due: 唔係有效日期,冇畫`);
  return `<div class="tl-note">${esc(bits.join(' · '))}</div>`;
}

export function timelineHTML(plan, todayStr) {
  const s = timelineStrip(plan, todayStr);
  if (s.status === 'no-history') return '';
  const today = s.todayPct == null ? ''
    : `<span class="tl-today" style="left:${s.todayPct.toFixed(2)}%"></span>`;
  return '<div class="tl">'
    + headHTML(s)
    + '<div class="tl-axis">'
    + `<span class="tl-bar" style="left:${s.barLeftPct.toFixed(2)}%;`
    + `width:${s.barWidthPct.toFixed(2)}%"></span>`
    + today
    + s.markers.map(markerHTML).join('')
    + '</div>'
    + `<div class="tl-scale"><span>${esc(s.axisStart)}</span>`
    + `<span>${esc(s.axisEnd)}</span></div>`
    + noteHTML(s)
    + '</div>';
}
```

- [ ] **Step 5: Splice it into the card**

In `docs/js/render-burndown.js`, add the import beside the existing two at the top:

```js
import { timelineHTML } from './render-timeline.js';
```

Then, in the `card.innerHTML` template (currently lines 80–83), add the strip after the chart box and before the caption. The `history_error` guard already short-circuits the chart; the strip needs the same treatment, and `timelineHTML` returns `''` for missing history anyway:

```js
    card.innerHTML = `<div class="t">${esc(repo.split('/').pop())}
        <span style="color:var(--muted)">· burndown(${esc(plan.path)})</span></div>
      ${plan.history_error ? '' : '<div class="chart-box"><canvas></canvas></div>'}
      ${plan.history_error ? '' : timelineHTML(plan, today)}
      ${caption ? `<div class="note" style="color:var(--muted)">${esc(caption)}</div>` : ''}`;
```

- [ ] **Step 6: Add the styles**

Append to `docs/css/dashboard.css`, directly after the `.burndown-card` block that ends at `:438`:

```css
/* Plan timeline 條:同一張卡入面,burndown 下面。條軸係 position:relative,
   啲 marker 用 left:% 定位,所以唔使 Chart.js —— Chart.js 4 冇 Gantt 型,
   為一條 bar 加個 CDN library 唔抵,而 CSS 版本 print 得出。 */
.tl { margin-top: 12px; }
.tl-head { font-size: var(--fs-xs); color: var(--muted); margin-bottom: 8px; }
.tl-head .tl-ok { color: var(--good); font-weight: 700; }
.tl-head .tl-warn { color: var(--warn); font-weight: 700; }
.tl-head .tl-bad { color: var(--alert); font-weight: 700; }
.tl-head .tl-muted { color: var(--muted); }
.tl-axis { position: relative; height: 22px; border-bottom: 1px solid var(--line); }
.tl-bar { position: absolute; top: 7px; height: 6px; border-radius: 3px; background: var(--line-strong); }
/* 今日線用返 render-burndown.js todayMarker 嗰個 #C4553B,唔用 var(--alert)
   (#C2452D)。兩條今日線喺同一張卡入面上下對住,差少少色會好突兀;canvas
   嗰邊讀唔到 CSS 變數,所以就係呢個字面值話事。 */
.tl-today { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px dashed #C4553B; }
.tl-mark {
  position: absolute; top: 3px; width: 12px; height: 12px; margin-left: -6px;
  border-radius: 50%; font-size: 9px; line-height: 12px; text-align: center;
  color: #fff; cursor: default;
}
.tl-overdue { background: var(--alert); }
.tl-soon7 { background: var(--warn); }
.tl-soon14 { background: #C9A227; }
.tl-later { background: var(--muted); }
.tl-scale { display: flex; justify-content: space-between; font-size: var(--fs-xs); color: var(--muted); margin-top: 4px; }
.tl-note { font-size: var(--fs-xs); color: var(--muted); margin-top: 6px; }
```

Token names verified against `docs/css/dashboard.css:7-24`: the palette is `--good` / `--warn` / `--alert`, plus `--muted`, `--line`, `--line-strong` and `--fs-xs`. Do not introduce new custom properties.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_frontend_timeline.py -v
```

Expected: 12 PASS.

Then the whole suite:

```bash
python -m pytest scripts/ -q
```

Expected: **367 passed** (330 baseline + 9 + 16 + 12). If `test_frontend_snapshot.py` fails, the rendered baseline changed on purpose — re-record with `python -m pytest scripts/test_frontend_snapshot.py --snapshot-update` and read the diff before committing.

- [ ] **Step 8: Commit**

```bash
git add docs/js/render-timeline.js docs/js/render-burndown.js docs/css/dashboard.css scripts/test_frontend_timeline.py scripts/fixtures/metrics-fixture-burndown.json
git commit -m "feat: plan timeline strip with SPI, due markers and a today line"
```

---

### Task 4: Document the strip

**Files:**
- Modify: `README.md` — the 「項目 Burndown」 section added by `03b0925`

**Interfaces:**
- Consumes: everything above. Produces no code.

- [ ] **Step 1: Write the section**

Append to `README.md`, directly after the 項目 Burndown section's 「讀之前要知」 bullet list:

````markdown
### Plan Timeline 條

同一張卡入面,burndown 下面多一條時間軸,答「邊件事、幾時到期」。**唔使加任何 config**,同 burndown 食同一份數據:

| 嘢 | 來源 |
|---|---|
| 條 bar(計劃窗口) | `plan.md` 第一個 commit → `due:` 推斷出嚟嘅目標日 |
| 每一粒 marker | `plan.open_tasks[]` 每個未做 task 嘅 `due:` |
| SPI | 完成 % ÷ 時間流逝 %。≥1 追得上、0.8–1 落後、<0.8 嚴重落後 |

Marker 顏色**淨係**講急切度(過期 / ≤7 日 / ≤14 日 / 之後);`!P1` 同 `#bug` 喺 tooltip 入面。同一日嘅 task 合成一粒,個數字就係嗰日有幾多件事。

**讀之前要知:**

- **條線只畫未做嘅 task。** `open_tasks` 得未打勾嗰啲,所以做完嘅嘢唔會留低痕跡 —— task 一路做完,條線一路變疏,就算冇任何嘢 slip 都一樣。「變疏」唔等於「順利」。
- **上限 50 個。** 一份超過 50 個未做 task 嘅 plan,條線會唔齊。
- **目標日多數係推斷嘅**(最遲嗰個 task due),同 burndown 一樣。冇一個用得嘅目標日就冇 SPI、冇「剩幾多日」,而條 bar 改為畫到今日 —— 卡上會講明係邊一種。
- **同 burndown 一樣唔跟** window selector(30/60/90/180)。
````

- [ ] **Step 2: Verify the docs match the code**

```bash
python -m pytest scripts/ -q
```

Expected: 367 passed. Then read the new README section against `docs/js/timeline.js` and confirm every claim holds — in particular that the SPI bands are `≥1` / `0.8–1` / `<0.8`, that markers group by date, and that nothing in the new code reads `state.windowDays`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the plan timeline strip and its limits"
```

---

## Verification

Before opening a PR:

```bash
python -m pytest scripts/ -q
```

Expected: **367 passed** (330 baseline + 9 Task 1 + 16 Task 2 + 12 Task 3).

Then look at it for real:

```bash
python3 -m http.server -d docs 8000
```

Open <http://localhost:8000>, go to 「項目 & 團隊」, and confirm AIFlowTesting's card shows the burndown chart with a timeline strip below it. Its plan has 11 dated open tasks running `2026-07-10` to `2026-09-18`, so expect a run of overdue markers on the left and a today line partway along. `docs/data/metrics.json` is gitignored; do not commit it.
