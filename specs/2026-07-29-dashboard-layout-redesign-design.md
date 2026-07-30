# Dashboard Layout Redesign — Design

**Date:** 2026-07-29
**Status:** Approved, not yet implemented
**Scope:** `docs/index.html`, `docs/css/dashboard.css`, `docs/js/tabs.js` (new), `docs/js/render-table.js`, `docs/js/main.js`, `scripts/test_frontend_snapshot.py`, `scripts/test_frontend_people.py`, `scripts/test_frontend_tabs.py` (new), `scripts/fixtures/rendered-baseline.json`, `README.md`

> Spec lives in `specs/` at repo root, **not** `docs/`. `docs/` is the published
> artifact root — anything placed there ships to Cloudflare Pages.

---

## 1. Problem

The dashboard renders every section it has, at the same visual weight, in one
unbroken scroll. Measured at 1440px viewport width with `?demo=1`:

| Section | Top offset | Height |
|---|---|---|
| `header.masthead` | 28 | 83 |
| `.kpis` (主 KPI) | 133 | 142 |
| `.kpis.dora` | 289 | 109 |
| 自動化水平分佈 | 412 | 293 |
| 每週趨勢 + 異常提醒 | 719 | 364 |
| 品質 × 自動化 | 1097 | 380 |
| 項目進度 | 1491 | 428 |
| Repo 概覽 | 1933 | 414 |
| Defect 追蹤 | 2360 | 291 |
| **最近 Tasks** | 2665 | **3946** |
| `footer` | 6633 | 17 |

**Total page height 6,689px — 6.7 screens.** The 最近 Tasks table is 3,946px of
that, **59% of the entire page**, holding 80 rows with no search, filter, or
paging. Every metric the dashboard exists to communicate lives in the top
2,665px; the remaining 60% is an append-only log.

### 1.1 Structural defects

| # | Defect | Where | Effect |
|---|---|---|---|
| 1 | Uniform card weight | [dashboard.css:101](../docs/css/dashboard.css) | Ten sections share one `.card` rule — same border, radius, padding — and every `h2` is 15px. `L3+ 自動化佔比`, which [README.md](../README.md) calls 「成個 dashboard 嘅北極星」, is styled identically to `MTTR(proxy)`. The eye gets no entry point |
| 2 | Eight equal-weight KPI tiles | [index.html:41-89](../docs/index.html) | Two rows of four. The DORA row is differentiated only by `font-size: 26px` vs `34px` ([dashboard.css:301](../docs/css/dashboard.css)) — an 8px delta carrying the whole primary/secondary distinction |
| 3 | Bar column is `1fr` | [dashboard.css:183](../docs/css/dashboard.css), [:271](../docs/css/dashboard.css), [:298](../docs/css/dashboard.css) | `.legend .row`, `.ov-row` and `.qrow` all stretch the bar track across the residual width — measured **988px** — stranding the count and percentage at the far right. Reading one row is a full-width eye sweep |
| 4 | Filters scroll away at 100px | [dashboard.css:38](../docs/css/dashboard.css) | `.masthead` is static. Changing repo / branch / person / window while reading row 60 of the task table means scrolling back to the top and losing position |
| 5 | Two visual languages | [dashboard.css:276](../docs/css/dashboard.css) | Everything is a white bordered card except `.contrib`, which is a filled `#F1F4F9` rounded chip with no border — the one element that breaks the system |
| 6 | L1/L2 near-invisible | [dashboard.css:10-11](../docs/css/dashboard.css) | `--l1: #CBD2D9` and `--l2: #9FB6D1` against `--card: #FFFFFF`. In the spectrum strip the two largest cohorts (42.2% and 16.2% of tagged tasks) read as empty space |

### 1.2 Confirmed rendering defect — every bar in the dashboard is invisible

`.bar-fill` is declared `height: 100%` with an inline `width` ([dashboard.css:191](../docs/css/dashboard.css))
and emitted as a bare `<span>`. **`width` and `height` do not apply to
non-replaced inline elements**, so the fill has never painted. `.bar-track`
escapes the same fate only by accident: it is a grid item, so it gets blockified.

Probed against the live page (`?demo=1`, 1440px):

```
#legend .bar-fill          display=inline  box=0.0x0.0    (style="width:16.216216216216218%;background:#CBD2D9")
#qLevels .bar-fill         display=inline  box=0.0x0.0    (style="width:30%;background:#CBD2D9")
#ovLangs .bar-fill         display=inline  box=0.0x0.0    (style="width:100%;background:#24407E")
#ovTypes .bar-fill         display=inline  box=0.0x0.0
#ovMonthly .bar-fill       display=inline  box=0.0x0.0
#projMilestones .bar-fill  display=inline  box=0.0x0.0
#legend .bar-track         display=block   box=988.0x8.0
```

Five emit sites, all with the same bug:

| Site | Renders |
|---|---|
| [render-kpi.js:72](../docs/js/render-kpi.js) | 自動化水平分佈 legend |
| [render-kpi.js:286](../docs/js/render-kpi.js) | 各 Level 修復佔比 |
| [render-project.js:73](../docs/js/render-project.js) | 項目完成度 |
| [render-project.js:86](../docs/js/render-project.js) | Milestone 進度 |
| [render-table.js:15](../docs/js/render-table.js) | Repo 概覽 — 語言構成 / commit types / 月度活躍 |

What section 1.1 defect 3 describes as "dead horizontal space" is therefore
partly a broken chart: a 988px grey rail with nothing drawn in it. **Fixing this
is a prerequisite for judging the layout**, because it changes what the affected
sections look like.

The fix is one declaration. It is logically independent of the redesign and
must land as its own commit so it can be reverted separately.

### 1.3 Decisions taken

| Question | Decision | Consequence |
|---|---|---|
| Restructure or restyle? | Overview + four tabs | Landing view drops from 6,689px to ~1,030px. Costs a new JS module and breaks three test assertions (§7) |
| Keep the visual identity? | Refine it | Beige paper, blue L1–L5 ramp, Space Grotesk / IBM Plex Mono / Noto Sans TC all stay. No dark mode |
| Task table | 25 rows + search + level filter + paging | `render-table.js` gains filter state; `rendered-baseline.json` must be regenerated |
| Tab panel hiding | `display: none`, elements never removed | All five render modules keep writing to the same IDs with zero changes. `wait_for_selector` defaults to `state="visible"` and breaks (§7) |
| Spec location | `specs/`, not `docs/superpowers/specs/` | `docs/` publishes to Cloudflare Pages. Matches the four existing specs |

---

## 2. Tab structure

A sticky chrome region holds the masthead, the filter controls, and the tab list.
Four panels below it.

| Tab | id | Contains | Est. height |
|---|---|---|---|
| 總覽 | `panel-overview` | KPI hero row, DORA strip, 自動化水平分佈, 每週趨勢 + 異常提醒 | ~1,030px |
| 品質 | `panel-quality` | RAG chips, 品質 grid, 各 Level 修復佔比, Defect 追蹤 | ~900px |
| 項目 & 團隊 | `panel-projects` | 項目進度, Repo 概覽, 貢獻者 | ~1,100px |
| Tasks | `panel-tasks` | 最近 Tasks + search + level filter + paging | ~1,200px |

Defect 追蹤 joins 品質 because a defect *is* a quality signal. Repo 概覽 joins
項目 because language mix and contributor counts describe the team and codebase,
not the automation metrics.

**Nothing is deleted.** Every section that renders today still renders; the
change is which ones share a screen.

### 2.1 Markup contract

Panels wrap existing sections without touching their internals:

```html
<div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
  <!-- existing <section class="kpis">, spectrum, duo — unmodified -->
</div>
```

This is the load-bearing constraint: **no element `id` moves, changes, or
disappears.** `render()` in [main.js:18](../docs/js/main.js) calls eleven render
functions that resolve elements by id through `$()`. All eleven keep working
untouched, including while their panel is hidden — `innerHTML` and `textContent`
writes do not require layout.

One exception needs care: `renderChart()` ([render-kpi.js:79](../docs/js/render-kpi.js))
draws to a `<canvas>` via Chart.js, which sizes from the element's client box. A
canvas inside `display: none` measures 0×0. 總覽 is the default active panel, so
the initial render is safe, but a `render()` triggered by a filter change while
another tab is active would produce a 0×0 chart. **Mitigation:** `tabs.js`
dispatches a `tab:shown` event on activation, and `main.js` calls
`state.chart?.resize()` when the overview panel becomes visible.

### 2.2 Behaviour

- Tab state lives in `location.hash` (`#quality`), so a tab is linkable and
  survives reload. Unknown or absent hash falls back to 總覽.
- Hash is **view** state; the existing `?owner=` param is **data** state
  ([main.js:103](../docs/js/main.js)). They are independent and must not
  interfere — `syncOwnerParam()` uses `history.replaceState` on
  `url.searchParams` only, so it already leaves the hash alone.
- Filter changes never change the active tab.
- `role="tablist"` / `role="tab"` / `role="tabpanel"`, `aria-selected`,
  `aria-labelledby`, and Left/Right/Home/End key handling per WAI-ARIA. Tabs are
  `<button>` elements so they are keyboard-reachable by default.

---

## 3. Visual system

Refinement of the existing identity, not a replacement.

### 3.1 Tokens

| Token | From | To | Why |
|---|---|---|---|
| `--ink` | `#191D1B` | `#161A18` | Slightly deeper for hero inversion contrast |
| `--muted` | `#6A7370` | `#667069` | Meets 4.5:1 on `--card` at 11.5px |
| `--line` | `#E2E4DD` | `#DDE0D8` | Card edges currently disappear against `--paper` |
| `--line-strong` | — | `#C7CCC2` | New: control borders and the chrome underline |
| `--l1` | `#CBD2D9` | `#B9C4CE` | Defect 6 — contrast on white 1.52:1 → 1.77:1 |
| `--l2` | `#9FB6D1` | `#8AA6C6` | Defect 6 — contrast on white 2.08:1 → 2.51:1 |
| `--good` | — | `#2E7D4F` | New: positive deltas. Reuses the RAG green already hardcoded at [render-kpi.js:210](../docs/js/render-kpi.js) |

`--l3` `#5F8CC6`, `--l4` `#2E5EB8`, `--l5` `#0A2F9C` are unchanged. The ramp must
stay monotonic in perceived darkness so the spectrum strip reads as a scale;
raising L1/L2 preserves that ordering.

**L1 and L2 still fail the WCAG 3:1 non-text contrast threshold**, and this is a
deliberate trade, not an oversight. `--l3` measures 3.47:1 and L4/L5 are darker
still, so only the two lightest steps are affected. Reaching 3:1 for L1 requires
roughly `#767F8A`, which would then force L2–L5 darker to stay distinguishable —
compressing five steps into the narrow dark end of the range and destroying the
"light = manual, dark = autonomous" reading the spectrum depends on.

The mitigation is redundancy, which is what WCAG 1.4.1 actually requires: colour
is never the sole carrier of information. Every legend row states its level code,
its name, its count and its percentage as text; every spectrum segment is
labelled `L1`–`L5` in-place. A reader who cannot distinguish `--l1` from `--l2`
loses no information. Do not "fix" the ratios by darkening the ramp.

### 3.2 Type scale

Currently 34 / 26 / 15 / 12. Becomes:

| Role | Size | Applied to |
|---|---|---|
| Hero value | 66px | `L3+ 自動化佔比` only |
| KPI value | 32px | The three other primary KPIs |
| DORA value | 21px | The four DORA metrics |
| Card heading | 14px | `h2` |
| Label / body | 11.5–12px | Labels, subs, notes |

### 3.3 Hero card

`L3+ 自動化佔比` becomes an inverted card — `--ink` background, white text —
spanning the first column of a `1.75fr 1fr 1fr 1fr` grid. It carries the 66px
value, the delta, a 6px inline spark bar showing the L1–L5 split, and a
plain-language sub ("185 個已分級 task 之中,77 個由 agent 主導完成").

The three secondary KPI cards **top-align their content** rather than stretching
to hero height — the mockup revealed they otherwise read as under-filled.

~~The existing `.warned` state needs a hero-specific colour.~~ **Withdrawn
during implementation:** `.warned` is toggled at
[render-kpi.js:33](../docs/js/render-kpi.js) on `#kpiCov` alone — the 分級覆蓋率
card, which is a plain card, never the hero. A `.kpi.hero .value.warned` rule
would be dead CSS for a state that cannot occur, so neither it nor the
`--hero-warn` token ships.

### 3.4 DORA strip

Four 109px cards collapse into one ~72px bordered strip: a
`grid-template-columns: repeat(4, 1fr)` row with `border-left` hairline dividers,
each cell holding label / value / sub inline. Preceded by a mono `DORA` eyebrow.

Preserved: `.scope-note` on 部署頻率 ([index.html:70](../docs/index.html)) and the
`–` empty state when no deployment record exists
([render-kpi.js:176](../docs/js/render-kpi.js)).

---

## 4. Density

### 4.1 The bar fix

```css
.bar-fill { display: block; height: 100%; border-radius: 4px; }
```

One declaration, resolving §1.2 at all five emit sites. No JS changes.

### 4.2 Fixed bar columns

| Rule | From | To |
|---|---|---|
| `.legend .row` | `44px 96px 1fr 52px 62px` | `34px 76px 200px 40px 52px` |
| `.qrow` | `44px 1fr 96px` | `44px 200px 96px` |
| `.ov-row` | `92px 1fr 76px` | `92px 200px 76px` |

Eye travel from label to value drops from ~988px to ~310px.

### 4.3 Two-up legend

`.legend` becomes `grid-template-columns: 1fr 1fr` above 1100px, collapsing to
one column below. Six rows become 3+3 — roughly half the vertical space and half
the horizontal sweep.

`renderSpectrum()` appends rows in a fixed order (L1…L5, then untagged) at
[render-kpi.js:63](../docs/js/render-kpi.js). CSS grid fills row-major, so a
two-column grid yields the column pairing L1/L4, L2/L5, L3/untagged. This is
acceptable — each row is self-labelled — and requires **no JS change**. Do not
use `grid-auto-flow: column` to "fix" the ordering: it would break the
single-column fallback.

### 4.4 Contributor cards

`.contrib` drops `background: var(--card2, #F1F4F9)` and adopts
`background: var(--card)` with `border: 1px solid var(--line)`, matching every
other surface. `.contrib.is-selected` keeps its outline affordance
([dashboard.css:351](../docs/css/dashboard.css)) — it is the click target for
person filtering.

---

## 5. Task table

Panel gains a control row above the table:

- **Search** — case-insensitive substring over title, author, and branch. Debounced 150ms.
- **Level filter** — L1–L5 / 未分級 / 全部 chips, single-select.
- **Paging** — 25 rows initially, 「載入更多」 appends 25. Caption reports 「顯示 25 / 214」.

Filter and page state live on `state` alongside the existing `state.sort`
([main.js:136](../docs/js/main.js)). Sorting, searching, or filtering resets the
page to 1; the existing sortable `thead` handlers keep working.

`renderTable()` gains a filter-then-slice step. The `⛔` violation and `⚠`
suspect markers must survive filtering — they are how 異常提醒 cross-references
rows ([render-kpi.js:147](../docs/js/render-kpi.js) says 「表格 ⛔ 標記咗涉事
rows」). Search matching runs against raw task fields, not rendered HTML, so
markup never affects results.

`thead` becomes `position: sticky` within the panel.

---

## 6. Print

Tabs hide 75% of the report from `window.print()`. The existing
`@media print` block ([dashboard.css:339](../docs/css/dashboard.css)) gains:

```css
@media print {
  [role="tabpanel"] { display: block !important; }
  .tabs, .controls { display: none; }
}
```

Printing then yields the full report as it does today. Paging still limits the
task table to the loaded rows — acceptable, and noted in the README.

---

## 7. Test impact

`text_content()` and `eval_on_selector()` read hidden elements fine, so most
assertions survive untouched. **Four** calls do not.

| Call | Problem | Fix |
|---|---|---|
| [test_frontend_snapshot.py:74](../scripts/test_frontend_snapshot.py) | `wait_for_selector("#taskRows tr")` defaults to `state="visible"`; `#taskRows` is in the Tasks panel, hidden at load | `state="attached"` |
| [test_frontend_people.py:44](../scripts/test_frontend_people.py) | Same | `state="attached"` |
| [test_frontend_people.py:189](../scripts/test_frontend_people.py) | `wait_for_selector("#projChips .chip-rag")` — 項目 panel hidden | `state="attached"` |
| [test_frontend_rework.py:41](../scripts/test_frontend_rework.py) | Same as the first. Missed in the original survey — its `open_dashboard()` helper gates every test in the module, so this single call failed nine tests | `state="attached"` |

A second correction found during implementation: a geometry assertion cannot be
made against a hidden panel either. `getBoundingClientRect()` returns 0 for any
element inside `display: none`, so the bars regression guard (§1.2) must walk
the tabs and measure whichever panel is showing.

`state="attached"` is the correct fix rather than clicking the tab first: these
tests assert *rendering*, not navigation. Tab activation gets its own test file.

**`scripts/fixtures/rendered-baseline.json` must be regenerated** with
`--snapshot-update`. `SECTION_IDS` includes `taskRows`, whose `innerHTML`
legitimately changes when paging cuts 80 rows to 25. Regeneration must happen
**after** the implementation is otherwise verified, and the diff must be
inspected — `strip`, `alertList`, `projChips`, `projMilestones`, `projLate`,
`projTodo` and `footStamp` are expected to be **byte-identical**, since no
renderer that produces them changes. Any diff in those seven is a bug, not a
baseline update.

New `scripts/test_frontend_tabs.py`:

| Test | Asserts |
|---|---|
| Default tab | 總覽 panel visible, other three hidden, `aria-selected` correct |
| Click switches | Clicking 品質 shows its panel and hides 總覽 |
| Hash deep-link | `#quality` loads with 品質 active |
| Unknown hash | `#nonsense` falls back to 總覽 |
| Keyboard | Right/Left/Home/End move the active tab |
| Filter preserves tab | `select_option("#personSel", …)` on 品質 leaves 品質 active |
| Chart resize | Switching away and back to 總覽 leaves `#weeklyChart` with non-zero width |
| Bars render | Every `.bar-fill` with a non-zero inline width has a non-zero rendered box — the §1.2 regression guard |
| Search filters | Typing an author name reduces `#taskRows tr` count |
| Level filter | Selecting L4 leaves only L4 rows |
| Paging | 25 rows initially; 「載入更多」 yields 50 |

The bars-render test is the one that must exist regardless of the redesign —
it is the regression guard for a defect that shipped unnoticed.

---

## 8. Files changed

| File | Change |
|---|---|
| `docs/index.html` | Sticky chrome; four `role="tabpanel"` wrappers; hero card markup; DORA strip; task-table control row. **No id changes** |
| `docs/css/dashboard.css` | Tokens, type scale, hero, DORA strip, `.bar-fill` fix, fixed bar columns, two-up legend, `.contrib` unification, sticky chrome and thead, print block |
| `docs/js/tabs.js` | **New**, ~60 lines. Activation, ARIA, keyboard, hash sync, `tab:shown` event |
| `docs/js/main.js` | Import `tabs.js`; resize chart on `tab:shown`; wire search / level-filter / paging handlers |
| `docs/js/render-table.js` | Filter-then-slice in `renderTable()`; caption reports shown/total |
| `scripts/test_frontend_snapshot.py` | One `state="attached"` |
| `scripts/test_frontend_people.py` | Two `state="attached"` |
| `scripts/test_frontend_tabs.py` | **New** |
| `scripts/fixtures/rendered-baseline.json` | Regenerated, diff inspected |
| `README.md` | Document the tab structure and the print caveat |

Five render modules — `render-kpi.js`, `render-project.js`, `people.js`,
`data.js`, `aggregate.js` — are **not modified**. `render-project.js` and
`render-kpi.js` benefit from the `.bar-fill` fix without changing.

### 8.1 Commit sequence

1. `fix: .bar-fill never rendered — inline spans ignore width` + the bars-render test. Independently revertable, and makes the current layout honest before it is judged.
2. `feat: tab structure` — panels, `tabs.js`, ARIA, hash, test file. Behaviour-only.
3. `feat: visual hierarchy` — tokens, type scale, hero, DORA strip.
4. `feat: density` — bar columns, two-up legend, `.contrib`.
5. `feat: task table search, filter, paging` + baseline regeneration.
6. `docs: README`.

Step 1 first is deliberate: it changes the rendered appearance of sections whose
layout steps 3–4 then tune, and conflating the two would make the baseline diff
unreadable.

---

## 9. Verification

- `python3 -m pytest scripts/ -v` green, including the regenerated baseline.
- Screenshot 總覽 at 1440px and confirm total page height is under 1,200px.
- Screenshot at 900px and 375px: KPI grid collapses, legend goes single-column, tabs remain reachable, no horizontal body scroll.
- `?demo=1` and the real data path both render.
- Tab through the chrome: focus order is masthead → controls → tabs → panel, and every tab is reachable without a mouse.
- `window.print()` preview shows all four panels.
- Grayscale the 總覽 screenshot and confirm every legend row and spectrum segment
  is still identifiable from its text alone (§3.1 — colour must stay redundant).

---

## 10. Out of scope

- Dark mode. Explicitly declined; the ramp would need re-picking for contrast on dark.
- Any change to metric definitions, aggregation, or `collect_github.py`. This is presentation only — every number keeps its current formula.
- Drill-down interaction (clicking a KPI to filter). Considered and declined in favour of tabs.
- Chart.js replacement. `renderChart()` keeps its current implementation and options.
- `.plan-bar`, `.pgrid`, `.plists`, `.plan-row`, `.plan-duo` ([dashboard.css:285-315](../docs/css/dashboard.css)) appear to be dead — no JS emits them. Removing dead CSS is a separate cleanup, not part of this change.
