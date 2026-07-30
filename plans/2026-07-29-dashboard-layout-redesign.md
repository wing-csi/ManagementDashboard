# Dashboard Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the dashboard from a 6,689px single scroll into an overview landing view behind four tabs, refine the visual hierarchy, and fix a defect that has kept every bar chart invisible since it shipped.

**Architecture:** Existing sections are wrapped in four `role="tabpanel"` containers and hidden with the `hidden` attribute — never removed from the DOM — so all eleven render functions keep resolving their targets by id with zero changes. A new `docs/js/tabs.js` owns activation, ARIA, keyboard navigation and `#hash` sync, and emits a `tab:shown` event that `main.js` uses to resize the Chart.js canvas after it has been laid out. Visual changes are almost entirely CSS.

**Tech Stack:** Vanilla ES modules, no build step. Chart.js 4.4.1 from CDN. Python 3 + pytest + pytest-playwright for tests. Static hosting via Cloudflare Pages from `docs/`.

**Spec:** [specs/2026-07-29-dashboard-layout-redesign-design.md](../specs/2026-07-29-dashboard-layout-redesign-design.md)

## Global Constraints

- **No element `id` may move, change, or be removed** from `docs/index.html`. Eleven render functions resolve targets by id via `$()`. This is the single load-bearing constraint of the whole change.
- Panels are hidden with the `hidden` attribute. Never `remove()`, never rebuild.
- `docs/` is the published artifact root — it ships to Cloudflare Pages. Never put specs, plans, or notes there.
- No build step. `docs/js/*.js` are ES modules loaded directly by the browser.
- Commit messages: `<type>: <description>`. No `Co-Authored-By` trailer — attribution is disabled globally and no commit in this repo carries one.
- Frontend tests intercept `**/data/metrics.json` with `page.route()`. **Never** swap `docs/data/metrics.json` on disk — it holds the operator's real private data locally.
- Colour must stay redundant: every legend row and spectrum segment carries its own text label. `--l1` and `--l2` sit below WCAG 3:1 non-text contrast by deliberate decision (spec §3.1). Do not darken the ramp to "fix" this.
- Level ramp must stay monotonic in perceived darkness: `--l1` lightest through `--l5` darkest.

---

### Task 1: Fix `.bar-fill` — every bar in the dashboard renders at 0×0

`.bar-fill` is a bare `<span>` carrying an inline `width`. Width and height do not apply to non-replaced inline elements, so no bar has ever painted. `.bar-track` survives only because it is a grid item and gets blockified.

**Files:**
- Modify: `docs/css/dashboard.css:191`
- Create: `scripts/test_frontend_bars.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. Pure CSS fix; no JS or markup changes. All five emit sites benefit without modification — `render-kpi.js:72`, `render-kpi.js:286`, `render-project.js:73`, `render-project.js:86`, `render-table.js:15`.

- [ ] **Step 1: Write the failing test**

Create `scripts/test_frontend_bars.py`:

```python
"""Every .bar-fill must actually paint.

Regression guard for a defect that shipped unnoticed: .bar-fill is emitted as
a bare <span> with an inline width, and width/height do not apply to
non-replaced inline elements. Every bar in the dashboard rendered at 0x0 —
the 自動化水平分佈 legend, 各 Level 修復佔比, 項目完成度, milestone progress,
and all three Repo 概覽 bar groups.

Run:  python -m pytest scripts/test_frontend_bars.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="bar rendering tests need pytest-playwright")

PROBE = """() => {
  return [...document.querySelectorAll('.bar-fill')]
    .map((el) => ({
      width: el.style.width,
      box: el.getBoundingClientRect().width,
      where: el.closest('[id]') ? el.closest('[id]').id : '?',
    }))
    .filter((b) => parseFloat(b.width) > 0);
}"""


def test_bar_fills_have_non_zero_width(page, server):
    """A .bar-fill with a non-zero inline width must occupy non-zero space."""
    page.goto(f"{server}/?demo=1", wait_until="networkidle")
    page.wait_for_selector(".bar-fill", state="attached")

    bars = page.evaluate(PROBE)
    assert bars, "no .bar-fill carried a non-zero inline width — probe is not exercising anything"

    collapsed = [b for b in bars if b["box"] == 0]
    assert not collapsed, (
        f"{len(collapsed)}/{len(bars)} bar fills rendered at zero width, e.g. "
        f"{collapsed[:3]}"
    )
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
python -m pytest scripts/test_frontend_bars.py -v
```

Expected: FAIL. Every probed bar reports `box: 0`, so `collapsed` equals `bars` and the assertion fires with a count matching the number of bars in the demo dataset.

- [ ] **Step 3: Apply the one-line fix**

In `docs/css/dashboard.css`, change line 191 from:

```css
.bar-fill { height: 100%; border-radius: 4px; }
```

to:

```css
/* display:block is load-bearing — a bare inline <span> ignores the inline
   width the renderers set, which kept every bar at 0x0. */
.bar-fill { display: block; height: 100%; border-radius: 4px; }
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
python -m pytest scripts/test_frontend_bars.py -v
```

Expected: PASS.

- [ ] **Step 5: Confirm nothing else broke**

```bash
python -m pytest scripts/ -v
```

Expected: all pass. `rendered-baseline.json` captures `innerHTML`, which this change does not touch — only computed layout changes, so the snapshot is unaffected. **If the snapshot test fails here, stop**: it means something other than CSS changed.

- [ ] **Step 6: Commit**

```bash
git add docs/css/dashboard.css scripts/test_frontend_bars.py
git commit -m "fix: .bar-fill never rendered — inline spans ignore width"
```

---

### Task 2: Tab structure

Wrap the existing sections in four panels and add navigation. Behaviour only — no visual restyling in this task.

**Files:**
- Modify: `docs/index.html` (wrap sections, add tab list, no id changes)
- Create: `docs/js/tabs.js`
- Modify: `docs/js/main.js`
- Modify: `docs/css/dashboard.css` (tab + chrome rules, print override)
- Create: `scripts/test_frontend_tabs.py`
- Modify: `scripts/test_frontend_snapshot.py:74`, `scripts/test_frontend_people.py:44,189`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `initTabs(): void` — wires listeners and activates the tab named by `location.hash`, falling back to `overview`.
  - `activate(name: string, opts?: { focus?: boolean }): void` — activates a panel; unknown names fall back to `overview`.
  - A `tab:shown` `CustomEvent` on `document`, with `detail: { tab: string }`.
  - Panel ids `panel-overview`, `panel-quality`, `panel-projects`, `panel-tasks`; tab ids `tab-overview`, `tab-quality`, `tab-projects`, `tab-tasks`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_frontend_tabs.py`:

```python
"""Tab navigation behaviour.

Panels are hidden, never removed — every render module writes to ids that must
stay resolvable while their panel is off-screen. These tests pin that, plus
ARIA state, keyboard navigation, hash deep-linking, and the Chart.js resize
that a canvas laid out inside a hidden panel would otherwise miss.

Run:  python -m pytest scripts/test_frontend_tabs.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_playwright",
                    reason="tab tests need pytest-playwright")

TABS = ["overview", "quality", "projects", "tasks"]


def open_dashboard(page, server, query: str = "?demo=1"):
    page.goto(f"{server}/{query}", wait_until="networkidle")
    page.wait_for_selector("#taskRows tr", state="attached")
    return page


def visible_panels(page) -> list[str]:
    return [t for t in TABS if page.is_visible(f"#panel-{t}")]


def test_overview_is_the_default_tab(page, server):
    open_dashboard(page, server)
    assert visible_panels(page) == ["overview"]
    assert page.get_attribute("#tab-overview", "aria-selected") == "true"
    assert page.get_attribute("#tab-quality", "aria-selected") == "false"


def test_hidden_panels_still_render_their_content(page, server):
    """The load-bearing constraint: renderers write to hidden panels fine."""
    open_dashboard(page, server)
    assert page.text_content("#taskRows").strip()
    assert page.text_content("#projChips").strip()
    assert page.text_content("#qRework").strip()


def test_clicking_switches_panels(page, server):
    open_dashboard(page, server)
    page.click("#tab-quality")
    assert visible_panels(page) == ["quality"]
    assert page.get_attribute("#tab-quality", "aria-selected") == "true"


def test_hash_deep_links_to_a_tab(page, server):
    open_dashboard(page, server, "?demo=1#quality")
    assert visible_panels(page) == ["quality"]


def test_unknown_hash_falls_back_to_overview(page, server):
    open_dashboard(page, server, "?demo=1#nonsense")
    assert visible_panels(page) == ["overview"]


def test_clicking_a_tab_updates_the_hash(page, server):
    open_dashboard(page, server)
    page.click("#tab-projects")
    assert page.evaluate("() => location.hash") == "#projects"


def test_arrow_keys_move_between_tabs(page, server):
    open_dashboard(page, server)
    page.focus("#tab-overview")
    page.keyboard.press("ArrowRight")
    assert visible_panels(page) == ["quality"]
    page.keyboard.press("ArrowLeft")
    assert visible_panels(page) == ["overview"]
    page.keyboard.press("End")
    assert visible_panels(page) == ["tasks"]
    page.keyboard.press("Home")
    assert visible_panels(page) == ["overview"]


def test_filter_change_preserves_the_active_tab(page, server):
    open_dashboard(page, server)
    page.click("#tab-quality")
    page.select_option("#windowSel", "30")
    assert visible_panels(page) == ["quality"]


def test_chart_recovers_size_after_returning_to_overview(page, server):
    """A canvas laid out while hidden measures 0x0 — tab:shown must resize it."""
    open_dashboard(page, server, "?demo=1#quality")
    page.click("#tab-overview")
    width = page.eval_on_selector("#weeklyChart", "el => el.getBoundingClientRect().width")
    assert width > 0


def test_owner_param_and_tab_hash_coexist(page, server):
    open_dashboard(page, server, "?demo=1&owner=Wing#quality")
    assert visible_panels(page) == ["quality"]
    assert "owner=Wing" in page.evaluate("() => location.search")
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
python -m pytest scripts/test_frontend_tabs.py -v
```

Expected: every test FAILs — `#panel-overview` does not exist yet, so `is_visible` returns False and `visible_panels` is empty.

- [ ] **Step 3: Create `docs/js/tabs.js`**

```js
/** Tab navigation for the dashboard's four panels.
 *
 * Panels are hidden with the `hidden` attribute, never removed: every render
 * module resolves its targets by id and must keep working while its panel is
 * off-screen. `innerHTML` and `textContent` writes do not need layout, so a
 * hidden panel renders correctly — with one exception, the Chart.js canvas,
 * which sizes from its client box. That is what `tab:shown` is for.
 */
const TABS = ['overview', 'quality', 'projects', 'tasks'];
const DEFAULT_TAB = 'overview';

const tabEl = (name) => document.getElementById(`tab-${name}`);
const panelEl = (name) => document.getElementById(`panel-${name}`);

export function activate(name, { focus = false } = {}) {
  const target = TABS.includes(name) ? name : DEFAULT_TAB;
  for (const t of TABS) {
    const on = t === target;
    const el = tabEl(t);
    el.setAttribute('aria-selected', String(on));
    // roving tabindex: one stop for the whole tablist, arrows move within it
    el.tabIndex = on ? 0 : -1;
    panelEl(t).hidden = !on;
  }
  if (focus) tabEl(target).focus();
  // replaceState does not fire hashchange, so this cannot loop
  if (location.hash.slice(1) !== target) {
    history.replaceState(null, '', `${location.pathname}${location.search}#${target}`);
  }
  document.dispatchEvent(new CustomEvent('tab:shown', { detail: { tab: target } }));
}

function onKeydown(e) {
  const i = TABS.indexOf(e.currentTarget.dataset.tab);
  if (i < 0) return;
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[e.key];
  if (next === undefined) return;
  e.preventDefault();
  activate(TABS[(next + TABS.length) % TABS.length], { focus: true });
}

export function initTabs() {
  for (const t of TABS) {
    tabEl(t).addEventListener('click', () => activate(t));
    tabEl(t).addEventListener('keydown', onKeydown);
  }
  activate(location.hash.slice(1));
  window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
}
```

- [ ] **Step 4: Restructure `docs/index.html`**

Replace the `<header class="masthead">…</header>` block (lines 21–39) with the sticky chrome. **The `<div class="wrap">` opening at line 11 moves below the chrome** so the chrome can span full width:

```html
<div class="chrome">
  <div class="chrome-inner">
    <header class="masthead">
      <div class="brand">
        <h1>自動化水平儀 <small>AI AUTONOMY GAUGE</small></h1>
        <div class="eyebrow" id="eyebrow">GITHUB TELEMETRY</div>
      </div>
      <div class="controls">
        <span class="badge-demo" id="demoBadge">DEMO 數據 · 手動要求(?demo=1)</span>
        <select id="repoSel" aria-label="Repo"></select>
        <select id="branchSel" aria-label="Branch"></select>
        <select id="personSel" aria-label="貢獻者"></select>
        <select id="windowSel" aria-label="統計範圍">
          <option value="30">近 30 日</option>
          <option value="60">近 60 日</option>
          <option value="90" selected>近 90 日</option>
          <option value="180">近 180 日</option>
        </select>
        <span class="stamp" id="stamp"></span>
      </div>
    </header>
    <div class="tabs" role="tablist" aria-label="Dashboard 分頁">
      <button class="tab" id="tab-overview"  data-tab="overview"  role="tab" aria-controls="panel-overview"  aria-selected="true">總覽</button>
      <button class="tab" id="tab-quality"   data-tab="quality"   role="tab" aria-controls="panel-quality"   aria-selected="false">品質</button>
      <button class="tab" id="tab-projects"  data-tab="projects"  role="tab" aria-controls="panel-projects"  aria-selected="false">項目 &amp; 團隊</button>
      <button class="tab" id="tab-tasks"     data-tab="tasks"     role="tab" aria-controls="panel-tasks"     aria-selected="false">Tasks</button>
    </div>
  </div>
</div>
```

Then wrap the existing sections, changing **nothing inside them**:

| Panel | Wraps existing sections |
|---|---|
| `panel-overview` | `.kpis`, `.kpis.dora`, `.spectrum-card`, `.duo` |
| `panel-quality` | `.card.quality`, `.card.defects` |
| `panel-projects` | `.card.projects`, `.card.overview` |
| `panel-tasks` | the final unclassed `<section class="card">` holding 最近 Tasks |

Each wrapper looks like:

```html
<div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
  <!-- existing sections, unmodified -->
</div>
```

`#loadError` and `<footer>` stay outside all panels — an error must show regardless of tab, and the footer belongs to the page.

- [ ] **Step 5: Wire `docs/js/main.js`**

Add the import at the top, beside the other module imports:

```js
import { initTabs } from './tabs.js';
```

Then in `init()`, immediately **before** the final `render()` call:

```js
  // A canvas laid out inside a hidden panel measures 0x0. Chart.js reads its
  // client box at construction, so re-measure whenever 總覽 becomes visible.
  document.addEventListener('tab:shown', (e) => {
    if (e.detail.tab === 'overview') state.chart?.resize();
  });
  initTabs();
  render();
```

- [ ] **Step 6: Add tab and chrome CSS**

Append to `docs/css/dashboard.css`:

```css
/* ---------- sticky chrome ---------- */
.chrome {
  position: sticky; top: 0; z-index: 20; background: var(--paper);
  box-shadow: 0 1px 0 var(--line), 0 8px 16px -14px rgba(0, 0, 0, 0.35);
}
.chrome-inner { max-width: 1380px; margin: 0 auto; padding: 0 24px; }
.brand { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }

/* ---------- tabs ---------- */
.tabs { display: flex; gap: 2px; border-bottom: 2px solid var(--ink); }
.tab {
  font-family: var(--font-display); font-size: 13.5px; font-weight: 500;
  color: var(--muted); background: none; border: 0;
  border-bottom: 2px solid transparent; margin-bottom: -2px;
  padding: 9px 16px; cursor: pointer;
}
.tab:hover { color: var(--ink); }
.tab:focus-visible { outline: 2px solid var(--l4); outline-offset: -2px; }
.tab[aria-selected="true"] { color: var(--ink); font-weight: 700; border-bottom-color: var(--ink); }
```

Replace the existing `@media print` block (line 339) with:

```css
@media print {
  .controls, .tabs { display: none; }
  /* tabs would otherwise hide 75% of the report from the printer */
  [role="tabpanel"][hidden] { display: block !important; }
  .chrome { position: static; box-shadow: none; }
  .card { border-color: #bbb; }
}
```

The `.masthead` rule keeps its existing declarations; only `margin-bottom` should drop to `0` now that the tab list sits beneath it.

- [ ] **Step 7: Fix the three visibility-dependent waits**

These assert *rendering*, not navigation, so `state="attached"` is the correct fix rather than clicking a tab first.

- `scripts/test_frontend_snapshot.py:74` → `page.wait_for_selector("#taskRows tr", state="attached", timeout=10_000)`
- `scripts/test_frontend_people.py:44` → `people_page.wait_for_selector("#taskRows tr", state="attached")`
- `scripts/test_frontend_people.py:189` → `page.wait_for_selector("#projChips .chip-rag", state="attached")`

- [ ] **Step 8: Run the full suite**

```bash
python -m pytest scripts/ -v
```

Expected: all pass, including the unchanged `rendered-baseline.json` — this task changes no renderer, so all eight snapshot sections must be byte-identical. **A snapshot failure here is a bug, not a baseline update.**

- [ ] **Step 9: Commit**

```bash
git add docs/index.html docs/js/tabs.js docs/js/main.js docs/css/dashboard.css scripts/test_frontend_tabs.py scripts/test_frontend_snapshot.py scripts/test_frontend_people.py
git commit -m "feat: overview + four tabs, panels hidden not removed"
```

---

### Task 3: Visual hierarchy — hero KPI and DORA strip

**Files:**
- Modify: `docs/css/dashboard.css` (tokens, type scale, hero, DORA strip)
- Modify: `docs/index.html` (hero markup, DORA strip markup — **no id changes**)

**Interfaces:**
- Consumes: the panel structure from Task 2.
- Produces: `.kpi.hero` and `.dora-strip` class contracts consumed by nothing else.

- [ ] **Step 1: Update the tokens**

In `docs/css/dashboard.css`, `:root` — change these six and add three:

```css
  --ink: #161A18;
  --muted: #667069;
  --line: #DDE0D8;
  --line-strong: #C7CCC2;
  --l1: #B9C4CE;
  --l2: #8AA6C6;
  --good: #2E7D4F;
  --hero-warn: #E0A93B;
```

`--l3`, `--l4`, `--l5` are unchanged. Do not darken them (Global Constraints).

- [ ] **Step 2: Restructure the KPI row markup**

In `docs/index.html`, the first `<section class="kpis">`: add `hero` to the first card's class and give it the spark bar and a richer sub. **`id="kpiL3"`, `id="kpiL3d"` must not change.**

```html
  <section class="kpis">
    <div class="card kpi hero">
      <div>
        <div class="label">L3+ 自動化佔比 — 北極星</div>
        <div class="value" id="kpiL3">–</div>
        <div class="delta" id="kpiL3d"></div>
      </div>
      <div class="hero-spark" id="heroSpark"></div>
      <div class="hero-foot">
        <div class="sub">task 由 agent 主導完成的比例</div>
        <span class="hero-tag">L3+L4+L5</span>
      </div>
    </div>
```

`#heroSpark` is populated in Task 4 Step 4. Leaving it empty here renders a zero-height flex row, which is visually inert — acceptable for one commit.

- [ ] **Step 3: Convert the DORA section to a strip**

Replace `<section class="kpis dora">…</section>` with:

```html
  <div class="dora-lead">DORA</div>
  <section class="dora-strip">
    <div class="d">
      <div class="dl">部署頻率<span class="scope-note" hidden>全 repo 範圍</span></div>
      <div class="dv" id="dDeploy">–</div>
      <div class="ds" id="dDeploySub">–</div>
    </div>
    <div class="d">
      <div class="dl">Lead Time(至 merge)</div>
      <div class="dv" id="dLead">–</div>
      <div class="ds">PR 開 → merge 中位數</div>
    </div>
    <div class="d">
      <div class="dl">變更失敗率(proxy)</div>
      <div class="dv" id="dCfr">–</div>
      <div class="ds">revert / hotfix ÷ 部署次數</div>
    </div>
    <div class="d">
      <div class="dl">MTTR(proxy)</div>
      <div class="dv" id="dMttr">–</div>
      <div class="ds">修復類 task 嘅 lead time 中位數</div>
    </div>
  </section>
```

All four ids and the `.scope-note` are preserved. `renderDora()` writes `.unit` spans into `#dDeploy` etc., so `.dv .unit` needs styling below.

- [ ] **Step 4: Add hero and strip CSS**

```css
/* ---------- KPI hierarchy ---------- */
.kpis { grid-template-columns: 1.75fr 1fr 1fr 1fr; align-items: start; }
.kpi .value { font-size: 32px; }
.kpi .delta.up { color: var(--good); }

.kpi.hero {
  background: var(--ink); border-color: var(--ink); color: #fff;
  display: grid; grid-template-rows: auto auto 1fr; padding: 18px 22px;
  align-self: stretch;
}
.kpi.hero .label { color: #A9B2AD; font-size: 12px; }
.kpi.hero .value { font-size: 66px; line-height: 0.95; }
.kpi.hero .value .unit { font-size: 26px; color: #A9B2AD; }
/* --warn fails contrast on --ink; the coverage warning needs its own value */
.kpi.hero .value.warned { color: var(--hero-warn); }
.kpi.hero .delta { font-size: 12.5px; margin-top: 8px; }
.kpi.hero .delta.up { color: #8FD3A6; }
.kpi.hero .delta.down { color: #F0A090; }
.kpi.hero .sub { color: #A9B2AD; }
.hero-spark { display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 14px; }
.hero-foot { display: flex; justify-content: space-between; align-items: flex-end; gap: 10px; margin-top: 6px; }
.hero-tag {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: #A9B2AD; border: 1px solid #3A423E;
  border-radius: 3px; padding: 2px 7px; white-space: nowrap;
}

/* ---------- DORA strip ---------- */
.dora-lead {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 6px;
}
.dora-strip {
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); margin-bottom: 14px; overflow: hidden;
}
.dora-strip .d { padding: 11px 18px; border-left: 1px solid var(--line); }
.dora-strip .d:first-child { border-left: 0; }
.dora-strip .dl { font-size: 11px; color: var(--muted); margin-bottom: 1px; }
.dora-strip .dv {
  font-family: var(--font-display); font-size: 21px; font-weight: 700;
  letter-spacing: -0.01em; line-height: 1.15;
}
.dora-strip .dv .unit { font-size: 12.5px; font-weight: 500; color: var(--muted); margin-left: 2px; }
.dora-strip .ds { font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); margin-top: 1px; }
@media (max-width: 900px) {
  .kpis { grid-template-columns: 1fr; }
  .dora-strip { grid-template-columns: repeat(2, 1fr); }
  .dora-strip .d:nth-child(3) { border-left: 0; }
}
```

Delete the now-dead `.kpis.dora .value { font-size: 26px; }` rule (line 301).

- [ ] **Step 5: Run the suite**

```bash
python -m pytest scripts/ -v
```

Expected: all pass. No renderer changed and no id moved, so the baseline is untouched.

- [ ] **Step 6: Commit**

```bash
git add docs/index.html docs/css/dashboard.css
git commit -m "feat: hero KPI and DORA strip give the north star real weight"
```

---

### Task 4: Density — fixed bar columns, two-up legend, unified cards

**Files:**
- Modify: `docs/css/dashboard.css`
- Modify: `docs/js/render-kpi.js` (populate `#heroSpark` only)

**Interfaces:**
- Consumes: `#heroSpark` from Task 3, `.bar-fill { display:block }` from Task 1.
- Produces: nothing consumed downstream.

- [ ] **Step 1: Fix the bar columns**

Three grid rules currently end in `1fr`, stretching the bar to ~988px and stranding numbers at the far right.

```css
.legend .row { grid-template-columns: 34px 76px 200px 40px 52px; }
.qrow { grid-template-columns: 44px 200px 96px; }
.ov-row { grid-template-columns: 92px 200px 76px; }
```

- [ ] **Step 2: Make the legend two-up**

Replace the `.legend` rule:

```css
/* Two columns above 1100px: halves both the vertical space and the
   label-to-value eye travel. Grid fills row-major, so the pairing is
   L1/L4, L2/L5, L3/untagged — each row is self-labelled, so that is fine.
   Do NOT use grid-auto-flow:column; it breaks the single-column fallback. */
.legend { margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 7px 40px; }
@media (max-width: 1100px) { .legend { grid-template-columns: 1fr; } }
```

- [ ] **Step 3: Unify the contributor cards**

`.contrib` is the only element not using the bordered-card language.

```css
.contrib {
  background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; padding: 12px 14px;
}
```

`.contrib.is-selected` keeps its existing outline — it is the click affordance for person filtering.

- [ ] **Step 4: Populate the hero spark bar**

In `docs/js/render-kpi.js`, at the end of `renderSpectrum(cur)` (after the legend loop closes, before the function's closing brace):

```js
  // Mirror of the strip, scaled into the hero card: composition and headline
  // read together instead of 300px apart.
  const spark = $('heroSpark');
  spark.innerHTML = LEVELS
    .map((l) => ({ l, n: cur.byLevel[l] }))
    .filter((s) => s.n > 0)
    .map((s) => `<span style="flex:${s.n};background:${META[s.l].color}"></span>`)
    .join('');
```

- [ ] **Step 5: Regenerate the baseline — deliberately**

`renderSpectrum()` now also writes `#heroSpark`, but `#heroSpark` is **not** in `SECTION_IDS`, so the eight captured sections are unaffected. Run the suite first and only regenerate if it actually fails:

```bash
python -m pytest scripts/ -v
```

Expected: PASS with no regeneration. **If the snapshot fails, stop and read the diff** — it would mean `renderSpectrum` altered `#strip`, which this step does not intend.

- [ ] **Step 6: Commit**

```bash
git add docs/css/dashboard.css docs/js/render-kpi.js
git commit -m "feat: fixed bar columns, two-up legend, unified contributor cards"
```

---

### Task 5: Task table — search, level filter, paging

**Files:**
- Modify: `docs/js/data.js:4` (state fields)
- Modify: `docs/js/aggregate.js:14` (`TABLE_CAP` → `PAGE_SIZE`)
- Modify: `docs/js/render-table.js`
- Modify: `docs/js/main.js` (handlers)
- Modify: `docs/index.html` (controls markup)
- Modify: `docs/css/dashboard.css`
- Modify: `scripts/test_frontend_tabs.py` (add table tests)
- Modify: `scripts/fixtures/rendered-baseline.json` (regenerate)

**Interfaces:**
- Consumes: `state` from `data.js`.
- Produces: `state.search: string`, `state.level: string` (`'all'` | `'L1'`…`'L5'` | `'none'`), `state.page: number` (1-based). `PAGE_SIZE: number = 25` exported from `aggregate.js`.

> **Spec correction:** §8 of the spec lists `aggregate.js` as unmodified. It changes by one line — `TABLE_CAP = 80` becomes `PAGE_SIZE = 25`. `TABLE_CAP` has exactly one consumer (`render-table.js`), so renaming is safe. Caps belong beside `DEFECT_CAP`, so this is the cohesive home.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_frontend_tabs.py`:

```python
from playwright.sync_api import expect


def open_tasks_tab(page, server):
    open_dashboard(page, server)
    page.click("#tab-tasks")
    return page


def test_table_pages_at_25_rows(page, server):
    open_tasks_tab(page, server)
    expect(page.locator("#taskRows tr")).to_have_count(25)
    assert "25 /" in page.text_content("#tableCap")


def test_load_more_appends_a_page(page, server):
    open_tasks_tab(page, server)
    page.click("#tableMore")
    expect(page.locator("#taskRows tr")).to_have_count(50)


def test_search_filters_rows(page, server):
    open_tasks_tab(page, server)
    before = page.locator("#taskRows tr").count()
    page.fill("#taskSearch", "webhook")
    expect(page.locator("#taskRows tr")).not_to_have_count(before)
    titles = page.eval_on_selector_all(
        "#taskRows tr td:nth-child(6)", "els => els.map(e => e.textContent.toLowerCase())")
    assert titles and all("webhook" in t for t in titles)


def test_level_filter_shows_only_that_level(page, server):
    open_tasks_tab(page, server)
    page.click('#levelFilter [data-level="L4"]')
    levels = page.eval_on_selector_all(
        "#taskRows tr td.lvlcell", "els => els.map(e => e.textContent.trim())")
    assert levels and all(t.startswith("L4") for t in levels)


def test_search_resets_paging(page, server):
    open_tasks_tab(page, server)
    page.click("#tableMore")
    expect(page.locator("#taskRows tr")).to_have_count(50)
    page.fill("#taskSearch", "fix")
    expect(page.locator("#taskRows tr")).to_have_count(25)
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
python -m pytest scripts/test_frontend_tabs.py -v -k "table or search or level or load_more"
```

Expected: FAIL — `#tableMore`, `#taskSearch`, `#levelFilter` do not exist, and the table still renders 80 rows.

- [ ] **Step 3: Add the state fields**

`docs/js/data.js` line 4 — append three fields to the `state` literal:

```js
export const state = { data: null, demo: false, windowDays: 90, repo: 'all', branch: 'all', person: 'all', personIndex: new Map(), chart: null, sort: { key: 'date', dir: -1 }, search: '', level: 'all', page: 1 };
```

- [ ] **Step 4: Rename the cap**

`docs/js/aggregate.js` line 14:

```js
export const PAGE_SIZE = 25;
```

- [ ] **Step 5: Add the controls markup**

In `docs/index.html`, inside the 最近 Tasks section, between `.card-head` and `.table-scroll`:

```html
    <div class="table-controls">
      <input type="search" id="taskSearch" placeholder="搜尋 title / author / branch" aria-label="搜尋 tasks">
      <div class="level-filter" id="levelFilter" role="group" aria-label="按 Level 篩選">
        <button class="lvbtn is-on" data-level="all">全部</button>
        <button class="lvbtn" data-level="L1">L1</button>
        <button class="lvbtn" data-level="L2">L2</button>
        <button class="lvbtn" data-level="L3">L3</button>
        <button class="lvbtn" data-level="L4">L4</button>
        <button class="lvbtn" data-level="L5">L5</button>
        <button class="lvbtn" data-level="none">未分級</button>
      </div>
    </div>
```

And after `.table-note`:

```html
    <button class="load-more" id="tableMore" hidden>載入更多</button>
```

- [ ] **Step 6: Filter and page in `render-table.js`**

Change the import on line 3:

```js
import { PAGE_SIZE, DEFECT_CAP, VIOLATION_META } from './aggregate.js';
```

Add above `renderTable()`:

```js
/** Search runs against raw task fields, never rendered HTML — markup must
 *  never affect what matches. */
function matchesFilters(t) {
  if (state.level !== 'all' && (t.level || 'none') !== state.level) return false;
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  return [t.title, t.author, t.branch].some((v) => (v || '').toLowerCase().includes(q));
}
```

In `renderTable()`, change line 119:

```js
  const rows = windowTasks().filter(matchesFilters);
```

Replace line 132:

```js
  const shown = rows.slice(0, state.page * PAGE_SIZE);
```

Replace line 144 and add the button state:

```js
  $('tableCap').textContent = rows.length
    ? `顯示 ${shown.length} / ${rows.length} 個 tasks` : '';
  $('tableMore').hidden = shown.length >= rows.length;
```

The `⛔` and `⚠` markers are inside the row template and survive filtering untouched — 異常提醒 cross-references them.

- [ ] **Step 7: Wire the handlers in `main.js`**

`renderTable` is already imported. Add **before** the existing four `change` listeners (currently line 131), so the page reset runs before the re-render reads it:

```js
  // Any scope change invalidates the current page offset
  for (const id of ['repoSel', 'branchSel', 'personSel', 'windowSel']) {
    $(id).addEventListener('change', () => { state.page = 1; });
  }
```

Then after the existing `windowSel` listener:

```js
  let searchTimer;
  $('taskSearch').addEventListener('input', (e) => {
    const v = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = v; state.page = 1; renderTable(); }, 150);
  });

  $('levelFilter').addEventListener('click', (e) => {
    const btn = e.target.closest('.lvbtn');
    if (!btn) return;
    state.level = btn.dataset.level;
    state.page = 1;
    for (const b of $('levelFilter').querySelectorAll('.lvbtn')) {
      b.classList.toggle('is-on', b === btn);
    }
    renderTable();
  });

  $('tableMore').addEventListener('click', () => { state.page += 1; renderTable(); });
```

In the existing sortable-`th` listener, reset the page:

```js
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : -1 };
    state.page = 1;
    renderTable();
```

- [ ] **Step 8: Style the controls**

```css
.table-controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
#taskSearch {
  font-family: var(--font-body); font-size: 12.5px; color: var(--ink);
  background: var(--card); border: 1px solid var(--line-strong);
  border-radius: 6px; padding: 6px 10px; min-width: 240px;
}
.level-filter { display: flex; gap: 4px; flex-wrap: wrap; }
.lvbtn {
  font-family: var(--font-mono); font-size: 11px; color: var(--muted);
  background: var(--card); border: 1px solid var(--line);
  border-radius: 999px; padding: 3px 10px; cursor: pointer;
}
.lvbtn:hover { color: var(--ink); }
.lvbtn.is-on { background: var(--ink); border-color: var(--ink); color: #fff; }
.load-more {
  font-family: var(--font-mono); font-size: 12px; color: var(--ink);
  background: var(--card); border: 1px solid var(--line-strong);
  border-radius: 6px; padding: 7px 16px; cursor: pointer; margin-top: 12px;
}
.load-more:hover { border-color: var(--ink); }
thead th { position: sticky; top: 0; background: var(--card); z-index: 1; }
```

- [ ] **Step 9: Run the new tests**

```bash
python -m pytest scripts/test_frontend_tabs.py -v
```

Expected: PASS.

- [ ] **Step 10: Regenerate the baseline and inspect the diff**

`#taskRows` legitimately changes from 80 rows to 25.

```bash
python -m pytest scripts/test_frontend_snapshot.py --snapshot-update
```

Then verify only `taskRows` moved:

```bash
python -c "import json,subprocess; old=json.loads(subprocess.run(['git','show','HEAD:scripts/fixtures/rendered-baseline.json'],capture_output=True,text=True).stdout); new=json.load(open('scripts/fixtures/rendered-baseline.json',encoding='utf-8')); print([k for k in old if old[k]!=new[k]])"
```

Expected output: `['taskRows']`. **Any other key in that list is a bug — stop and investigate.** The other seven sections come from renderers this task does not touch.

- [ ] **Step 11: Run the full suite**

```bash
python -m pytest scripts/ -v
```

Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add docs/index.html docs/css/dashboard.css docs/js/data.js docs/js/aggregate.js docs/js/render-table.js docs/js/main.js scripts/test_frontend_tabs.py scripts/fixtures/rendered-baseline.json
git commit -m "feat: task table search, level filter and paging"
```

---

### Task 6: Verify and document

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Screenshot at three widths and check the numbers**

Serve `docs/` and capture 1440 / 900 / 375. Confirm: 總覽 total page height under 1,200px; KPI grid collapses at 900; legend single-column below 1100; no horizontal body scroll at 375.

- [ ] **Step 2: Check colour redundancy**

Grayscale the 1440px 總覽 screenshot. Every legend row and spectrum segment must still be identifiable from its text alone (Global Constraints).

- [ ] **Step 3: Keyboard pass**

Tab from the top: masthead → controls → tab list. Arrow keys move within the tab list. Every panel reachable without a mouse.

- [ ] **Step 4: Print preview**

`window.print()` must show all four panels.

- [ ] **Step 5: Document in `README.md`**

Add to the dashboard section: the four tabs and what each holds, `#hash` deep-linking, and the print caveat — printing shows all panels but the task table prints only the rows loaded so far.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document the tab structure and print caveat"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| §1.2 bar defect | Task 1 |
| §2 tab structure, ARIA, hash, chart resize | Task 2 |
| §3.1 tokens, §3.2 type scale, §3.3 hero, §3.4 DORA strip | Task 3 |
| §4.1 bar fix | Task 1 |
| §4.2 fixed columns, §4.3 two-up legend, §4.4 contributors | Task 4 |
| §5 task table | Task 5 |
| §6 print | Task 2 Step 6 |
| §7 test fixes, baseline, new tests | Tasks 1, 2, 5 |
| §9 verification | Task 6 |

**Deviation from spec:** `aggregate.js` gains a one-line rename (`TABLE_CAP` → `PAGE_SIZE`), which spec §8 lists as unmodified. Flagged inline in Task 5.

**Type consistency:** `state.search` / `state.level` / `state.page` are declared in Task 5 Step 3 and consumed in Steps 6–7 under those exact names. `PAGE_SIZE` is defined in Step 4 and imported in Step 6. `activate()` / `initTabs()` / `tab:shown` are defined in Task 2 Step 3 and consumed in Step 5. Panel and tab ids match between Task 2 Steps 3, 4 and the tests in Step 1.
