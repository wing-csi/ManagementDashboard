# Stale-Data Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a banner between the header and the tab row when `metrics.json` is more than 48 hours old, so a stalled nightly pipeline stops looking like fresh data.

**Architecture:** One new pure module, `docs/js/staleness.js`, decides the status from `generated_at` and a caller-supplied "now". `main.js` calls it once at load — and never in demo mode — then toggles a single element. Nothing else changes: `refDate()` and every date-derived calculation are deliberately left alone.

**Tech Stack:** Vanilla ES modules, no build step. pytest + pytest-playwright, Python 3.11+ stdlib.

**Source spec:** [`specs/2026-08-05-stale-data-indicator-design.md`](../2026-08-05-stale-data-indicator-design.md)

## Global Constraints

- **No new dependencies.** No `package.json`, no build step, no new CDN `<script>` tag.
- **No collector change, no new `config.toml` key, no new `metrics.json` field.** The banner reads only `generated_at`, which ships today.
- **Do not touch `refDate()`** (`docs/js/data.js:71`) or any calculation deriving "today" from `generated_at` — spec §8. This is warn-only.
- **`staleness()` must never call `Date.now()` internally.** "Now" is always a parameter. Spec §3: without this, every test pinned to a fixture date rots into failure as the calendar advances.
- **User-facing strings are Cantonese**, matching every existing card in `docs/js/`.
- **No `font-size` px literals anywhere** — not in CSS outside `:root`, not inline in JS or HTML. `scripts/test_frontend_typography.py::test_no_font_size_literal_survives_outside_the_token_block` regexes the files as text, so even a comment quoting one trips it. Use `var(--fs-xs)`.
- **Minimum visible text is 12px** (`MIN_FONT_PX`). `--fs-xs` is exactly 12px, so it is the floor — do not go below it.
- **Existing CSS tokens only** (`docs/css/dashboard.css:3-26`): `--alert` `#C2452D`, `--warn` `#A8751B`, `--muted`, `--card`, `--line`, `--radius`, `--fs-xs`. Do not introduce new custom properties.
- **The full suite must stay green:** `python -m pytest scripts/ -q` — **369 passed** today. Every task adds; none subtracts.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/js/staleness.js` (create) | `staleness(generatedAt, nowMs)` and `stalenessMessage(s)`. Pure, DOM-free, no imports. |
| `docs/index.html` (modify) | One element between `</header>` (`:32`) and `<div class="tabs">` (`:33`). |
| `docs/js/main.js` (modify) | Import and call it after the stamp at `:79-81`; skip entirely in demo mode. |
| `docs/css/dashboard.css` (modify) | `.stale-banner` and two modifier classes. |
| `scripts/test_staleness_js.py` (create) | Unit tests for the pure module. |
| `scripts/test_frontend_staleness.py` (create) | Playwright rendering tests. |
| `README.md` (modify) | Document the banner and its limits. |

Dependencies run one way: `staleness.js` ← `main.js`. Nothing imports `main.js`.

> **Checked before writing this plan — the snapshot baseline does NOT need regenerating.**
> `scripts/test_frontend_snapshot.py:29-32` captures exactly eight ids: `strip`,
> `alertList`, `taskRows`, `projChips`, `projMilestones`, `projLate`, `projTodo`,
> `footStamp`. The banner is a sibling of `<header>` and `.tabs`, inside none of them.
> This matters because `scripts/fixtures/metrics-fixture.json` is dated `2026-07-20`
> and *will* render the banner during those tests — it just is not captured.

---

### Task 1: `staleness.js` — the pure decision

**Files:**
- Create: `docs/js/staleness.js`
- Test: `scripts/test_staleness_js.py` (create)

**Interfaces:**
- Consumes: nothing (first task)
- Produces, all from `docs/js/staleness.js`:
  - `STALE_MS: number` (48 hours in ms), `FUTURE_TOLERANCE_MS: number` (1 hour in ms)
  - `staleness(generatedAt: string|null|undefined, nowMs: number) -> {status, ageDays}` where `status` ∈ `'fresh' | 'stale' | 'unreadable' | 'future'` and `ageDays` is a `number` only when `status === 'stale'`, otherwise `null`
  - `stalenessMessage(s: object) -> string` — the Cantonese sentence, `''` when `status === 'fresh'`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_staleness_js.py`:

```python
"""Unit tests for docs/js/staleness.js, executed in a real browser.

Same approach as test_plan_dates_js.py: no JS test runner exists in this repo,
so the ES module is imported inside a Playwright page and asserted there.

Every case pins "now" to a fixed number and derives the timestamp from it, so
these tests do not drift as the real calendar advances. That is the same
property the module's signature exists to give the frontend tests.

Run:  python -m pytest scripts/test_staleness_js.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="staleness.js unit tests need pytest-playwright")

# 一個固定嘅「而家」。實際係邊一日唔重要 —— 重要係佢唔郁。
NOW = 1_800_000_000_000


def evaluate(page, server, body: str):
    page.goto(f"{server}/?demo=1", wait_until="domcontentloaded")
    return page.evaluate(
        "async () => { const m = await import('/js/staleness.js'); "
        f"return ({body}); }}"
    )


def at(offset_expr: str) -> str:
    """由 NOW 推出一個 ISO 時間戳,offset 用 JS 表達式寫(正數 = 舊)。"""
    return f"new Date({NOW} - ({offset_expr})).toISOString()"


def test_data_from_this_morning_is_fresh(page, server):
    """20 個鐘大係正常 —— cron 21:00 UTC 行,一日入面大部分時間都係咁。"""
    got = evaluate(page, server, f"m.staleness({at('20*3600e3')}, {NOW})")
    assert got == {"status": "fresh", "ageDays": None}


def test_exactly_forty_eight_hours_is_still_fresh(page, server):
    """界線係 `>`,唔係 `>=`。啱啱 48 鐘唔算過期。"""
    got = evaluate(page, server, f"m.staleness({at('48*3600e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_a_minute_past_forty_eight_hours_is_stale(page, server):
    got = evaluate(page, server, f"m.staleness({at('48*3600e3 + 60e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 2}


def test_age_days_floors_instead_of_rounding(page, server):
    """84 個鐘係 3.5 日 —— 要出「3 日前」,唔係 4。門檻用毫秒判,呢個數淨係
    攞嚟寫嗰句字。"""
    got = evaluate(page, server, f"m.staleness({at('84*3600e3')}, {NOW})")
    assert got == {"status": "stale", "ageDays": 3}


def test_a_missing_timestamp_is_unreadable_not_stale(page, server):
    """冇時間戳唔等於數據舊 —— 要改嘅嘢完全唔同,所以要分得開。"""
    got = evaluate(page, server, f"m.staleness(null, {NOW})")
    assert got == {"status": "unreadable", "ageDays": None}


def test_a_malformed_timestamp_is_unreadable(page, server):
    got = evaluate(page, server, f"m.staleness('唔係一個日期', {NOW})")
    assert got["status"] == "unreadable"


def test_a_future_timestamp_says_the_clock_is_wrong(page, server):
    """時間戳喺未來代表有個 clock 唔啱,唔係數據舊。講成「舊咗」就係講假嘢。"""
    got = evaluate(page, server, f"m.staleness({at('-2*3600e3')}, {NOW})")
    assert got == {"status": "future", "ageDays": None}


def test_small_clock_skew_is_tolerated(page, server):
    """半個鐘嘅偏差好平常 —— 唔可以為咗佢彈個警告出嚟。"""
    got = evaluate(page, server, f"m.staleness({at('-30*60e3')}, {NOW})")
    assert got["status"] == "fresh"


def test_fresh_data_produces_no_message(page, server):
    """冇嘢講嗰陣要出空字串,唔可以出 'undefined' 落個 banner 度。"""
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('1*3600e3')}, {NOW}))")
    assert got == ""


def test_the_stale_message_names_the_age_and_what_to_check(page, server):
    """個 banner 要講得出係幾耐同埋去邊度查 —— 淨係話「舊咗」等於冇講。"""
    got = evaluate(
        page, server,
        f"m.stalenessMessage(m.staleness({at('5*864e5')}, {NOW}))")
    assert "5 日前" in got
    assert "Actions" in got
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_staleness_js.py -v
```

Expected: all 10 FAIL — the dynamic `import('/js/staleness.js')` rejects because the file does not exist.

- [ ] **Step 3: Create `docs/js/staleness.js`**

```js
/** 數據新鮮度 —— 純計算,冇 DOM,所以可以獨立測。
 *
 *  「而家」係一個參數,唔係喺入面 call Date.now()。呢點唔係風格問題:模組自己
 *  攞當前時間嘅話,測試就冇得釘住「而家」,而所有用固定 fixture 嘅 test 會隨住
 *  月曆行前慢慢變紅(metrics-fixture-burndown.json 釘咗 2026-08-04)。同
 *  burndownSeries(plan, todayStr) 同 timelineStrip(plan, todayStr) 收 today
 *  做參數,係同一個做法。
 *
 *  呢度**只係出提示,唔掂任何計算**。過期嗰陣,refDate() 同條今日線一律照用
 *  generated_at 做今日,即係照舊唔準 —— 個 banner 講嘅係「唔好信呢頁幾新」,
 *  唔係幫你修正啲數(spec §7)。
 */

const HOUR = 3600e3;
const DAY = 864e5;

/** 過期線:48 個鐘。
 *
 *  唔係 24 —— pipeline 每日 05:00 HKT(21:00 UTC)行,所以一日入面大部分時間,
 *  最新可能嘅數據本身已經 20 幾個鐘大。一條「超過 24 鐘」嘅規矩會每日下晝都嘈
 *  一次,而嘈得滯嘅提示等於冇提示。48 鐘代表至少一次 run 真係冇出到嘢。 */
export const STALE_MS = 48 * HOUR;

/** 時間戳喺未來幾多先當個 clock 唔啱。平時嘅 skew 食得起,唔好為佢彈警告。 */
export const FUTURE_TOLERANCE_MS = HOUR;

/** `{status, ageDays}`。
 *
 *  四個 status 要分得開,因為每個要講嘅嘢同要改嘅嘢都唔同:冇時間戳唔等於數據
 *  舊,而未來嘅時間戳代表 browser clock 或者 collector 有問題。併埋一齊就係
 *  講緊一件假嘢。
 *
 *  `ageDays` 淨係喺 'stale' 嗰陣有數 —— 另外三種都冇一個講得出口嘅「幾多日前」。 */
export function staleness(generatedAt, nowMs) {
  const ms = typeof generatedAt === 'string' ? Date.parse(generatedAt) : NaN;
  if (!Number.isFinite(ms)) return { status: 'unreadable', ageDays: null };

  const age = nowMs - ms;
  if (age < -FUTURE_TOLERANCE_MS) return { status: 'future', ageDays: null };
  // 門檻用毫秒判,唔用日數判:啱啱 48 鐘係 fresh,但佢已經係「2 日」。用日數
  // 判嘅話 49 鐘同 71 鐘都係 2,一個應該出一個唔應該出,就分唔開。
  if (age > STALE_MS) return { status: 'stale', ageDays: Math.floor(age / DAY) };
  return { status: 'fresh', ageDays: null };
}

/** 每個 status 有自己嘅講法 —— 跟返 timeline spec §8「每一個缺席都要自己解釋」。
 *  三句都要講得出「去邊度查」,淨係話「有問題」等於冇講。 */
const MESSAGE = {
  stale: (s) => `數據係 ${s.ageDays} 日前嘅 —— nightly pipeline 可能停咗。`
    + '去 GitHub Actions 睇下最近嘅 collect run 紅咗未。',
  unreadable: () => '讀唔到數據嘅時間戳,所以唔知呢頁係幾時嘅數。'
    + '查 metrics.json 個 generated_at。',
  future: () => '數據嘅時間戳喺未來 —— 部機或者 collector 個時間唔啱。'
    + '呢頁所有「今日」、「過期」、SPI 都信唔過。',
};

export function stalenessMessage(s) {
  const build = MESSAGE[s.status];
  return build ? build(s) : '';
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/test_staleness_js.py -v
```

Expected: 10 PASS.

- [ ] **Step 5: Run the whole suite**

```bash
python -m pytest scripts/ -q
```

Expected: **379 passed** (369 baseline + 10 new). Nothing renders yet, so no existing test can move.

- [ ] **Step 6: Commit**

```bash
git add docs/js/staleness.js scripts/test_staleness_js.py
git commit -m "feat: decide whether metrics.json is stale, as a pure function"
```

---

### Task 2: Render the banner

**Files:**
- Modify: `docs/index.html:32` (insert one line after `</header>`)
- Modify: `docs/js/main.js:1-10` (import) and `:79-81` (after the stamp)
- Modify: `docs/css/dashboard.css` — append after the `.stamp` rule at `:177`
- Test: `scripts/test_frontend_staleness.py` (create)

**Interfaces:**
- Consumes: `staleness(generatedAt, nowMs)` and `stalenessMessage(s)` from `./staleness.js` (Task 1)
- Produces: element `#staleBanner`, hidden when fresh; classes `stale-banner` plus `sb-stale` / `sb-unreadable` / `sb-future`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_frontend_staleness.py`:

```python
"""數據過期提示條嘅渲染守則。

Fixture 個日期由 Python 相對「而家」計出嚟,唔係寫死 —— 寫死嘅話呢個檔自己就會
變成下一個「今日過、聽日紅」嘅計時炸彈,正正係整份設計要避開嗰樣嘢。

Run:  python -m pytest scripts/test_frontend_staleness.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("pytest_playwright",
                    reason="staleness rendering tests need pytest-playwright")

FIXTURE = Path(__file__).parent / "fixtures" / "metrics-fixture.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ago(**kw) -> str:
    """相對而家嘅 ISO 時間戳。正數 = 幾耐之前。"""
    stamp = datetime.now(timezone.utc) - timedelta(**kw)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")


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


def _with_stamp(stamp: str) -> dict:
    data = _load()
    data["generated_at"] = stamp
    return data


def test_five_day_old_data_raises_the_banner(page, server):
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert "5 日前" in dash.inner_text("#staleBanner")


def test_this_mornings_data_raises_nothing(page, server):
    """20 個鐘大係正常。喺度嘈嘅話,真係停咗嗰日就冇人會信呢條 banner。"""
    _serve(page, _with_stamp(_ago(hours=20)))
    dash = _open(page, server)
    dash.wait_for_selector("#taskRows tr", state="attached")
    assert dash.is_hidden("#staleBanner")


def test_demo_mode_never_raises_the_banner(page, server):
    """Demo 數據個 generated_at 死咗喺 2026-07-06,永遠過期。喺度長期掛住一條
    banner,只會訓練啲人當佢透明。"""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector("#demoBadge.on", state="attached")
    assert page.is_hidden("#staleBanner")


def test_the_banner_is_announced_politely(page, server):
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert dash.get_attribute("#staleBanner", "role") == "status"


def test_a_broken_timestamp_says_so_instead_of_guessing_an_age(page, server):
    _serve(page, _with_stamp("唔係一個日期"))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    text = dash.inner_text("#staleBanner")
    assert "讀唔到" in text
    assert "日前" not in text


def test_a_future_timestamp_blames_the_clock_not_the_data(page, server):
    stamp = (datetime.now(timezone.utc)
             + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    _serve(page, _with_stamp(stamp))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert "時間唔啱" in dash.inner_text("#staleBanner")


def test_the_banner_cannot_be_dismissed(page, server):
    """撳得走嘅提示一定俾人撳走,撳走就返返去「睇唔見」—— 即係原本要修嗰個問題。"""
    _serve(page, _with_stamp(_ago(days=5)))
    dash = _open(page, server)
    dash.wait_for_selector("#staleBanner", state="visible")
    assert dash.eval_on_selector_all(
        "#staleBanner button, #staleBanner [role=button]", "els => els.length") == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/test_frontend_staleness.py -v
```

Expected: FAIL — `#staleBanner` does not exist.

- [ ] **Step 3: Add the element to `docs/index.html`**

Insert one line immediately after `</header>` (`:32`), before `<div class="tabs"` (`:33`):

```html
    <div class="stale-banner" id="staleBanner" role="status" hidden></div>
```

`role="status"` announces politely to a screen reader without stealing focus. There is deliberately no dismiss control.

- [ ] **Step 4: Wire it up in `docs/js/main.js`**

Add to the existing imports at the top of the file:

```js
import { staleness, stalenessMessage } from './staleness.js';
```

Then, directly after the two stamp lines at `:79-81`, add:

```js
  // 數據過期提示。Demo 模式唔計 —— demo 個 generated_at 死咗喺度,幾大都唔
  // 代表任何嘢,而 #demoBadge 已經講緊你喺 demo 入面。
  const stale = state.demo ? null : staleness(data.generated_at, Date.now());
  const banner = $('staleBanner');
  if (!stale || stale.status === 'fresh') {
    banner.hidden = true;
    banner.textContent = '';
  } else {
    banner.textContent = stalenessMessage(stale);
    banner.className = `stale-banner sb-${stale.status}`;
    banner.hidden = false;
  }
```

`state.demo` is already assigned at `:55`, well before this point.

- [ ] **Step 5: Add the styles**

Append to `docs/css/dashboard.css`, directly after the `.stamp` rule at `:177`:

```css
/* 數據過期提示條:header 同 tabs 中間,所以每個分頁都見到。
   唔俾撳走 —— 撳得走嘅提示一定俾人撳走,撳走之後就返返去「睇唔見」,
   即係原本要修嗰個問題。 */
.stale-banner {
  margin: 0 0 12px;
  padding: 10px 14px;
  border: 1px solid var(--alert);
  border-radius: var(--radius);
  background: var(--card);
  color: var(--alert);
  font-size: var(--fs-xs);
  /* 1.6 俾中文行距鬆啲;唔設 white-space,等佢喺窄螢幕自己斷行 ——
     test_no_horizontal_overflow_at_supported_widths 最窄查到 375px。 */
  line-height: 1.6;
}
.stale-banner[hidden] { display: none; }
/* 呢兩個唔係「數據舊咗」,係「講唔出佢幾舊」—— 用 warn 唔用 alert。 */
.sb-unreadable, .sb-future { border-color: var(--warn); color: var(--warn); }
```

Token names verified against `docs/css/dashboard.css:3-26`. Do not add new custom properties, and do not write a `font-size` px literal — see Global Constraints.

- [ ] **Step 6: Run the new tests to verify they pass**

```bash
python -m pytest scripts/test_frontend_staleness.py -v
```

Expected: 7 PASS.

- [ ] **Step 7: Run the whole suite**

```bash
python -m pytest scripts/ -q
```

Expected: **386 passed** (369 baseline + 10 + 7).

> **The snapshot baseline must NOT need updating.** `scripts/fixtures/metrics-fixture.json`
> is dated `2026-07-20`, so the banner *will* be on screen during
> `test_frontend_snapshot.py` — but `SECTION_IDS` (`:29-32`) captures eight ids and the
> banner is inside none of them. If that test goes red, something placed the banner in
> the wrong part of the DOM; fix the placement rather than running `--snapshot-update`.

- [ ] **Step 8: Commit**

```bash
git add docs/index.html docs/js/main.js docs/css/dashboard.css scripts/test_frontend_staleness.py
git commit -m "feat: warn on the page when metrics.json has gone stale"
```

---

### Task 3: Document the banner

**Files:**
- Modify: `README.md` — the 「線上睇」 section, beside the two pipeline bullets added by `28db7df`

**Interfaces:**
- Consumes: everything above. Produces no code.

- [ ] **Step 1: Write the section**

In `README.md`, replace the 「睇唔出數據舊咗」 bullet (added by `28db7df`, which says the page gives no sign) with:

````markdown
- **數據舊咗會出提示**:`generated_at` 超過 **48 鐘**,header 同分頁中間會出一條
  banner,講明係幾多日前嘅數同去邊度查。48 唔係 24 —— cron 21:00 UTC 行,一日
  入面大部分時間最新嘅數據本身已經 20 幾個鐘大,一條 24 鐘嘅規矩會每日下晝都
  嘈一次。時間戳讀唔到、或者喺未來(部機時間唔啱),會出唔同嘅講法,唔會當成
  「舊咗」。Demo 模式唔出。
- **但佢淨係捉得到 pipeline 停咗,捉唔到 deploy 停咗。** CI 綠燈但 wrangler 靜靜哋
  乜都冇上到嘅話,`generated_at` 照樣行前,banner 唔會出聲。
- **提示淨係入版嗰陣計一次。** 開住個 tab 過咗週末返嚟,見到嘅仲係星期五嗰個
  判斷 —— 撳 refresh 先啱。
- **出咗提示都唔會改啲數。** 過期嗰陣「過期 task 數」、SPI、條今日線一律照用
  `generated_at` 做今日,即係照舊唔準。Banner 講嘅係「唔好信呢頁幾新」,唔係
  幫你修正啲數。
````

- [ ] **Step 2: Verify the docs match the code**

```bash
python -m pytest scripts/ -q
```

Expected: 386 passed. Then read the new README bullets against `docs/js/staleness.js` and confirm every claim holds — in particular that the threshold is 48 hours, that demo mode is skipped in `main.js`, and that nothing in the new code touches `refDate()`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the stale-data banner and its limits"
```

---

## Verification

Before opening a PR:

```bash
python -m pytest scripts/ -q
```

Expected: **386 passed** (369 baseline + 10 Task 1 + 7 Task 2).

Then look at it for real:

```bash
python3 -m http.server -d docs 8000
```

Open <http://localhost:8000>. `docs/data/metrics.json` is whatever `sync_data.py` last wrote, so the banner may or may not appear — to force it, temporarily edit that file's `generated_at` to a date a week back and reload. Confirm the banner sits between the header and the tab row, stays visible across all four tabs, and wraps rather than overflowing when the window is narrowed to 375px (the narrowest width `WIDTHS` covers, at `scripts/test_frontend_typography.py:33`). `docs/data/metrics.json` is gitignored; do not commit it.
