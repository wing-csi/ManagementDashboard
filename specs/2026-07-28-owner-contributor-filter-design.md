# Owner / Contributor Filter — Design

**Date:** 2026-07-28
**Status:** Approved, not yet implemented
**Scope:** `config.toml`, `scripts/collect_github.py`, `docs/js/*`, `docs/index.html`

> Spec lives in `specs/` at repo root, **not** `docs/`. `docs/` is the published
> artifact root — anything placed there ships to Cloudflare Pages.

**Supersedes** the ~15-line sketch at
[`specs/2026-07-27-dashboard-enhancements-design.md`](2026-07-27-dashboard-enhancements-design.md)
§#3 "Owner filter — Phase 2". Two points of that sketch are corrected here:

| Sketch said | Corrected |
|---|---|
| 16 distinct authors | **18** — re-counted against live `metrics.json` (§2) |
| Aliases go in `[classify.author_aliases]` | Top-level `[people]` (§4) — aliases are identity, not AI-level classification, and grouping by human reads better than a flat identity→identity map |

---

## 1. Problem

The dashboard has no person dimension. A team lead cannot see one person's
workload, and a developer cannot isolate their own tasks. Today the only filters
are repo, branch, and date window ([docs/index.html:26-37](../docs/index.html)).

Two distinct facts about people exist, and conflating them would be wrong:

| Fact | Source | Meaning |
|---|---|---|
| **Contributor** | `tasks[].author` (derived) | who wrote the code |
| **Project owner** | config (declared) | who is accountable for a repo |

Ownership is a property of a *repo*; contribution is a property of a *task*. They
get separate axes (§5.2, §5.3).

## 2. Confirmed data problem: split identities

The live `metrics.json` held **2,048 tasks across 18 distinct authors** when this
was written (the dataset grows nightly — it was 2,054 a few hours later, so treat
every count here as a dated snapshot, not an invariant). Two of those authors are
the same human:

- `wing-csi` — 375 tasks (repo-owner account)
- `wing2036` — 78 tasks (this machine's collaborator credential)

Verified end-to-end after implementation: with the alias declared, the two
collapse into a single `Wing` entry whose count is exactly their sum, while the
Author column still shows which account did each task.

`'Shane'` (9 tasks) is a raw git commit name, not a GitHub login:
[`collect_github.py:515-517`](../scripts/collect_github.py) falls back to
`author.name` when a commit has no linked GitHub user.

Without identity merging, a lead filtering `wing-csi` silently misses 78 tasks.
This is the single most important correctness requirement of the feature.

## 3. Architecture

```
config.toml                    collect_github.py            metrics.json
  [people]              ──▶    validate + resolve    ──▶     people: {...}
  [[repos]] owner = ".."       (fail fast on error)          repo_meta[r].owner
                                                                    │
                                                                    ▼
                                                            docs/js/people.js
                                                     author → person index (built once)
                                                                    │
                                 state.person ─────────────────────┤
                                 state.repo   ─────────────────────┤
                                                                    ▼
                                              data.js tasksBetween() ──▶ all renders
```

Person filtering flows through the single existing choke point,
`tasksBetween()` ([docs/js/data.js:30-37](../docs/js/data.js)), so all
task-derived sections re-scope without per-section plumbing.

### 3.1 Why the frontend resolves aliases, not the collector

Considered stamping a `person` field on every task in the collector. Rejected:
2,048 tasks × ~20 bytes ≈ **41 KB (~3.4%)** added to a ~1.2 MB `metrics.json`,
and every alias edit rewrites all rows.

Chosen instead: the collector emits the **map only** (a few hundred bytes) and
`docs/js/people.js` builds the lookup once at load. Consequences:

- One config location (`config.toml`); validation stays in Python where the
  868-line test suite already lives.
- `tasks[].author` stays **raw**, so the Author column still shows *which
  account* did the work while the filter groups by human. No information lost.

## 4. Configuration

```toml
# Optional. Unmapped identities pass through as themselves.
[people]
Wing = ["wing-csi", "wing2036"]

[[repos]]
name = "example-org/example-repo"
owner = "Wing"            # optional; resolved through [people]
```

### 4.1 Validation (collector, fail fast)

Errors — exit non-zero, name the culprit, **before** `metrics.json` is written,
so a bad config never half-writes data:

| Condition | Rationale |
|---|---|
| An identity listed under two canonical people | Ambiguous resolution |
| A canonical name colliding with a raw author present in tasks | Ambiguous resolution |
| Empty identity list for a person | Certainly a mistake |
| Non-string entry in a list | Type error at the boundary |

Warning (stderr, non-fatal) — an `owner` value matching no canonical person and
no task author. This catches the `owner = "Wng"` typo **without** rejecting a
legitimate owner who never commits (e.g. a manager).

### 4.2 Schema

`schema_version` stays at **2**. Both additions are optional and both directions
degrade gracefully: an old `metrics.json` yields an identity map and omits the
owner grouping; an old frontend ignores unknown keys. Bumping would falsely
signal that consumers must update.

## 5. Frontend components

### 5.1 New module `docs/js/people.js` (~60 lines)

Keeps `data.js` focused. Pure functions, no DOM:

```js
buildPersonIndex(peopleMap)          // {"Wing":["wing-csi","wing2036"]} → Map<author, person>
personOf(author)                     // falls back to the raw author when unmapped
personOptions(tasks, repo, branch)   // [{person, count}] sorted by count desc
```

### 5.2 Contributor dropdown

`<select id="personSel">` after `branchSel` in the masthead. Enabled even at
全部 repos — unlike branch, a person **is** comparable across repos.

- Options: `全部成員`, then `Wing (453)` — count descending.
- Rebuilt when repo or branch changes; scoped to the current repo/branch but
  **not** the date window, so options don't flicker when switching 30/90/180 日.
- If the selected person has no tasks in the new scope, resets to 全部 — the
  same fallback the branch select already uses
  ([docs/js/main.js:71](../docs/js/main.js)).

### 5.3 Owner grouping on the repo axis

Ownership *is* repo-scoping, so it lives in the repo select rather than a fourth
control:

```html
<select id="repoSel">
  <option value="all">全部 repos</option>
  <optgroup label="按負責人">
    <option value="owner:Wing">Wing 的項目 (3)</option>
  </optgroup>
  <optgroup label="個別 repo"> … </optgroup>
</select>
```

The two axes stay orthogonal and compose: *"Wing's projects, work done by Tony"*
is expressible. The owner also shows as a chip on each repo in 項目進度 and
Repo 概覽; repos with no declared owner show 未指定.

If no repo declares an owner, the 「按負責人」 optgroup is omitted entirely and
the dropdown looks exactly as it does today.

### 5.4 Required refactor: `repoInScope()`

`state.repo` now holds `'all'`, a repo name, **or** `'owner:Wing'`. Ten sites
currently test `state.repo !== 'all' && repo !== state.repo` directly, and every
one of them would silently match nothing under an owner value:

`data.js:32` · `aggregate.js:122` · `aggregate.js:136` · `render-kpi.js:220` ·
`render-project.js:35, :76, :92` · `render-table.js:22, :45, :76`
(verified at `f530f36`; find them with `grep -rn "state.repo !== 'all'" docs/js/`)

All ten are replaced with one exported predicate `repoInScope(repo)`, plus
`singleRepo()` (returns a repo name or `null`) to drive the branch-select
disable — branch names remain incomparable across repos, so an owner selection
disables branch exactly as 全部 repos does.

This removes duplicated logic rather than adding to it.

### 5.5 URL state

`?owner=Wing` is read on load and written with `history.replaceState`; the param
is dropped at 全部. Only the person filter gets URL state — repo/branch/window
stay in-memory as today.

**Security.** The `?owner=` value is untrusted. It is used **only** for equality
comparison against the known person list and discarded on no match. It never
reaches `innerHTML`; `?owner=<img onerror=…>` renders nothing. Option labels come
from data, escaped with the existing `esc()`.

A stale bookmark (`?owner=` naming someone since removed) falls back to 全部
silently with no error box — that path is a stale link, not a failure.

## 6. Behaviour when a person is selected

Most sections re-scope correctly through `windowTasks()`. Three places do not,
and are handled explicitly rather than left to produce authoritative-looking
wrong numbers.

| Section | Behaviour | Reason |
|---|---|---|
| KPIs, 自動化水平分佈, 每週 chart, 異常提醒, 品質 qgrid, commit types, 月度活躍, 最近 Tasks | re-scope | task-derived |
| DORA Lead Time, MTTR | re-scope | task-derived (`cur.leads`, `cur.fixLeads`) |
| **變更失敗率** | shows `–` + sub-text stating it needs repo-wide scope | `cur.failTasks / deployEvents` ([render-kpi.js:187](../docs/js/render-kpi.js)) would divide one person's reverts by the whole repo's deploys |
| 部署頻率 | unchanged, marked 「全 repo 範圍」 | `metaInWindow()` is repo-level; no person dimension exists |
| 品質 RAG | unchanged, marked; `repoRag()` **pins `state.person = 'all'`** | it calls `windowTasks()` ([render-kpi.js:192-197](../docs/js/render-kpi.js)), so without pinning its CI pass rate silently becomes one person's PRs while coverage/security stay repo-wide |
| 項目進度, Defect 追蹤, 語言構成 | unchanged, marked | issue/repo-level, no person dimension |
| **貢獻者** | stays team-wide, selected person highlighted | it is the comparison view *and* where you pick from; filtering it to one 100% bar destroys its purpose |

`月度活躍` ([render-table.js:45](../docs/js/render-table.js)) filters
`state.data.tasks` by hand instead of going through `tasksBetween()`, so it needs
the person predicate applied explicitly.

The eyebrow gains `· 負責人 Wing` so a filtered dashboard cannot be misread as
team-wide. All scope markers live **outside** the eight snapshot section ids, so
the default render is unaffected.

## 7. Testing

### 7.1 Python (existing pytest suite)

- `[people]` parsing: valid map, section absent, section empty.
- Each validation failure in §4.1 → non-zero exit, culprit named, **no
  `metrics.json` written**.
- Owner: parsed per repo, alias-resolved, emitted to `repo_meta[repo].owner`,
  warning on unrecognised name.

### 7.2 Frontend (Playwright driven from pytest)

`scripts/fixtures/metrics-fixture.json` and `rendered-baseline.json` stay
**untouched** — with the filter at 全部 the render must remain byte-identical,
which is the strongest available regression guard. New tests use a separate
`metrics-fixture-people.json`.

New cases:

1. Selecting a person narrows 最近 Tasks to that person, **including
   alias-merged tasks** (the `wing-csi` + `wing2036` case).
2. `?owner=Wing` deep link applies on load.
3. Hostile / unknown `?owner=` → 全部, no error box, nothing injected.
4. Person selected → `#dCfr` shows `–`.
5. Person selected → 貢獻者 still lists more than one person.
6. `owner:Wing` scopes repos and disables the branch select.
7. Switching repo so the selected person has no tasks → resets to 全部.

### 7.3 Coverage note

The Python changes are unit-covered. There is **no JS test runner in this repo**
(no `package.json`), so the frontend gets behavioural coverage only — no
line-coverage number. Introducing a JS runner is a larger change than this
feature warrants and is deliberately out of scope.

## 8. Out of scope

- **Multi-select** — one person at a time, matching the existing single-select
  filters. Comparing two people side by side is a different feature.
- **Filtering issues by assignee** — 項目進度 and Defect 追蹤 stay repo-scoped.
  Issue assignees are a disjoint population from task authors; merging them is a
  separate decision. (The older spec's note about raising `assignees(first:2)`
  therefore stays unactioned.)
- **Reviewer identity** — not retained by the collector; unchanged from the
  older spec's finding.
- **Automatic identity detection** — `metrics.json` carries no author email to
  key on. Aliases are declared, not guessed.
