# Management Dashboard — 8 Feature Enhancements

**Date:** 2026-07-27
**Status:** Approved design, ready for implementation planning
**Analysis by:** Fable 5 (three parallel agents) · **Implementation:** Opus 5 / Sonnet 5

> Spec lives in `specs/` at repo root, **not** `docs/`. `docs/` is the GitHub Pages
> artifact root (`.github/workflows/collect.yml:48`), so anything placed there is
> published to the public web. This document describes authentication architecture
> and a live data exposure; it must not be published.

---

## 1. Current architecture

A static dashboard fed by a scheduled Python collector. No server, no build step.

```
config.toml ──▶ collect_github.py (GitHub Actions, daily 05:00 HKT)
                       │
                       ▼
             docs/data/metrics.json (~1.2 MB, overwritten each run)
                       │
                       ▼
             docs/index.html (vanilla JS, Chart.js from CDN) ──▶ GitHub Pages
```

| Component | File | Size |
|---|---|---|
| Collector | `scripts/collect_github.py` | 964 lines |
| Tests | `scripts/test_collect_github.py` | 868 lines |
| Frontend | `docs/index.html` | 1349 lines (CSS + HTML + JS inline) |
| Config | `config.toml` | 13 tracked repos |
| Deploy | `.github/workflows/collect.yml` | Pages artifact, `contents: read` |

The system is mature: an L1–L5 AI-automation classifier, DORA proxies, governance
red-line detection, and claim-vs-behaviour verification. The eight requirements land
on top of substantial existing machinery — in several cases on machinery that already
implements them.

---

## 2. Findings that reframe the requirements

Four discoveries from the analysis materially change what the work is.

### 2.1 The dataset is 99.75% direct commits

2,023 of 2,028 tasks are direct pushes; **5** are merged PRs. Every PR-derived metric
in the dashboard is computing over a sample of five. This single fact invalidates the
naive reading of requirement #8 and caps the value of any PR-based signal.

### 2.2 Requirement #8 is not imprecise — it is structurally dead

`rework` counts only human `CHANGES_REQUESTED` reviews on PRs
(`scripts/collect_github.py:404`, assigned at `:638`). `collect_commits`
(`:495-541`) never sets it, so direct commits keep the dataclass default of `0`.

**Live distribution across all 2,028 tasks: `{0: 2028}`.** Not one non-zero value.

Meanwhile the signals this team *does* generate are uncollected:

- **41 revert-titled tasks** exist in the data; the collector never flags them
  (only a frontend regex at `docs/index.html:591` sees them).
- **"Reopened" is never queried.** `ISSUES_QUERY` (`:140-169`) fetches neither
  `stateReason` nor `timelineItems(itemTypes:[REOPENED_EVENT])`.
- **"Failed QA" is invisible.** `_ci_state` (`:579-582`) reads `statusCheckRollup`
  of the *last commit only*. A PR that failed CI five times and passed on the sixth
  reports `pass`.
- **Dismissed reviews vanish.** A `CHANGES_REQUESTED` later dismissed becomes
  `DISMISSED` and stops counting — rework retroactively disappears.
- **Closed-unmerged PRs drop their rework entirely** (`:596-599`), discarding
  arguably the strongest signal.

### 2.3 Requirements #5 and #6 are ~80% built but starved of data

The UI exists: `今日建議優先處理` (`docs/index.html:487-504`, rendered `:1151-1154`),
milestone progress bars (`:1087-1096`), completion chips (`:1057-1083`).

But **no planning data reaches it**:

- `issues` is `None` for **12 of 13 repos** — the `benegg` and `abci` tokens lack
  Issues:Read.
- `collect_issues` (`:780-826`) swallows that failure silently at `:785-786`,
  returning `None` with **no entry in `errors`** — so the dashboard cannot even
  report that it is blind.
- **No repo configures `plan_file`** (`config.toml:21` is commented out).

The pipes are laid; nothing flows through them.

### 2.4 A live bug on the requirement #5 path

`issueScore` is declared **twice**:

- `docs/index.html:763-773` — returns a **number**, uses `PRIORITY_RE` (`:743-747`)
- `docs/index.html:1034-1049` — returns an **object** `{sc, why}`

Function declarations hoist, so the second wins. The sort at `:1151` computes
`issueScore(b) - issueScore(a)` = `object - object` = **`NaN`**, making the
comparator a no-op.

**The "today's suggested priorities" list has been rendering unsorted.** The first
declaration and `PRIORITY_RE` are dead code. This is a textbook monolith collision:
two features each added a scoring helper and silently clobbered each other.

### 2.5 No history is retained — burn-down is impossible today

`collect_github.py:955` does `args.out.write_text(...)` to a single path. The active
workflow deploys `docs/` as a Pages artifact with `contents: read` and **never commits
output back**. Each deploy fully replaces the last; prior days are unrecoverable.

Plan checkboxes carry no completion timestamps, `closedRecent` issues are capped at 30
(`:153`), and milestones expose only current counts. **No backfill is possible.** A
burn-down chart requires a new append-only aggregate file and accrues only from ship day.

---

## 3. Security finding (verified first-hand, 2026-07-27)

| Check | Result |
|---|---|
| `wing-csi/ManagementDashboard` visibility | **public** |
| `https://wing-csi.github.io/ManagementDashboard/data/metrics.json` | **HTTP 200 anonymous**, 1,181,417 bytes |
| `benegg/BOCPT-CMS-API`, `Tony-Liu-1248/abci-crm`, `benegg/BoostBank-ReactNative-SMEApp` | **HTTP 404 anonymous → private** |

**2,023 of 2,028 tasks in the public file belong to private repos**, each with its
commit/PR title, plus 16 author logins, branch names, and issue metadata.

| Tasks | Private repo |
|---|---|
| 1,861 | `benegg/BoostBank-ReactNative-SMEApp` |
| 100 | `Tony-Liu-1248/abci-crm` |
| 25 | `benegg/BOCPT-CMS-API` |
| 24 | `benegg/BOCPT-EE-Web` |
| 62 | six other `benegg/*` repos |

Source code is not exposed; titles, authorship and branch names are. `README.md:290`
already warns: *"hub public + target private = 漏緊嘢"* — the live deployment violates
its own documented rule.

**A client-side login would not have fixed this.** On GitHub Pages any gate is browser
JavaScript while the JSON stays fetchable at a stable URL.

### Accepted risk (explicit user decision)

The user was shown this evidence twice and **elected to keep the repo public**, gating
the dashboard only. Recorded as an accepted risk. Consequences that remain live:

1. Pre-existing `metrics.json` snapshots stay readable in public git history
   (`chore: update metrics [skip ci]` commits, 2026-07-22).
2. Anyone who already cloned or forked retains a copy.

**Mitigation adopted instead of privacy** (see §5.3): once delivery moves to
Cloudflare, `metrics.json` is removed from the repo and never committed again, so the
*current* dataset stops being publicly readable while the repo stays public. Flipping
the repo to private later remains a one-step change requiring no redesign.

### Requirement #1's second clause rests on a wrong premise

"Prevents unauthorized data modification" — there is **no write path anywhere**. No
POST/PUT/form submission exists in `docs/index.html`; the workflow runs `contents: read`
(`collect.yml:11-14`). Modification is already prevented by GitHub repository
permissions. A dashboard login contributes nothing to it. Report this back to whoever
raised the requirement.

---

## 4. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Repo stays **public**; gate the dashboard only | User decision, informed. Offset by §5.3 |
| D2 | Auth = GitHub OAuth + **collaborator check**, via Cloudflare Worker | Auto-syncs with repo access; no separate allowlist |
| D3 | Planning source = **`plan_file` markdown** per repo | Avoids the Issues:Read permission blocker; feeds #5, #6 and #2 at once |
| D4 | Rework = **commit-level** (reverts + repeat-fixes) | Only definition that yields non-zero signal in a direct-push culture |
| D5 | **Split `docs/index.html`** into CSS + ES modules | 1349 lines vs. an 800 cap; §2.4 is a direct symptom |
| D6 | SPDT = additional GitHub repos, names supplied at implementation | Config-only; mechanism already exists |

---

## 5. Target architecture

### 5.1 Delivery

The collector is unchanged in *kind* — GitHub Actions, Python, daily cron. Only
delivery changes.

```
config.toml ─▶ collect_github.py (Actions) ─▶ metrics.json + history.json
                                                       │
                                            upload to Cloudflare R2
                                                       │
   viewer ─▶ Cloudflare Worker ─▶ GitHub OAuth ─▶ collaborator check ─▶ serve
```

### 5.2 The Worker (new, and the only new service)

Responsibilities, each independently testable:

| Unit | Responsibility |
|---|---|
| `oauth.js` | GitHub OAuth code exchange; no session logic |
| `authorize.js` | Given a login, decide allow/deny. **Pure function over an injected GitHub client** |
| `session.js` | Signed cookie issue/verify; no GitHub knowledge |
| `serve.js` | Static asset + R2 object serving, gated on a valid session |

**Authorization rule.** Allow if *either*:
- the login is a collaborator on ≥1 repo listed in `config.toml`, **or** a member of
  the `benegg` org; **or**
- the account's **verified primary email** ends in the configured Chinasoft domain.

Both the org name and the email domain are Worker configuration values, not hardcoded
constants. The exact Chinasoft domain string is an input required before Phase 3
(§9.5).

"Login with GitHub" alone authorizes nobody — every human has a GitHub account. The
collaborator/org check is what makes it a control.

Sessions are short-lived (≤24 h) so revoked repo access takes effect within a day.
Collaborator lookups are cached per session to stay inside API rate limits.

### 5.3 Removing the repo copy of `metrics.json`

1. `git rm docs/data/metrics.json`, and gitignore the path.
2. CI generates it into a temp path and uploads to R2; it is never committed.
3. The frontend fetches from the Worker origin rather than `./data/metrics.json`.

Net effect: the current dataset stops being publicly readable **without** changing repo
visibility. Historical snapshots remain in git history until separately purged — a
follow-up the user may take at any time.

### 5.4 Frontend restructure (D5)

`index.html` keeps only the skeleton. Split along the seams the existing comment
banners already mark:

| File | Contents | ~lines |
|---|---|---|
| `docs/css/dashboard.css` | the inline `<style>` (`:8-351`) | 350 |
| `docs/js/data.js` | fetch + window/repo/branch filter state (`:610-618`) | 120 |
| `docs/js/aggregate.js` | KPIs, weekly buckets, DORA proxies (`:620-773`) | 250 |
| `docs/js/render-kpi.js` | KPI row, spectrum strip, alerts | 250 |
| `docs/js/render-project.js` | progress, milestones, today's tasks | 300 |
| `docs/js/render-table.js` | task table, sorting | 200 |
| `docs/data/demo-data.js` | the 80 KB inline `DEMO_DATA` blob (`:576`) | 1 |

All within the 200–400 line target.

**Known trade-off:** ES modules do not run over `file://`, so local preview requires
`python3 -m http.server -d docs 8000` instead of opening the file directly. Accepted.

`state` (`:604`) is a mutable singleton and `render()` (`:1282-1298`) rebuilds all
sections wholesale. The split does **not** attempt to fix this; converting to immutable
state updates is explicitly out of scope to keep the refactor behaviour-preserving.

---

## 6. Per-requirement design

### #1 Authorization — Phase 3

Per §5.2. Deliverables: Worker source under `worker/`, `wrangler.toml`, a CI step
replacing `deploy-pages`, and unit tests for `authorize.js` covering: collaborator
allowed, non-collaborator denied, org member allowed, Chinasoft email allowed,
unverified email denied, GitHub API failure denies (fail closed).

### #2 Fix / User Request — Phase 1

New `Task` field `work_type: "bug" | "feature" | "other"`, set by a classification
ladder mirroring the existing AI-level pattern:

1. **PR label** (`bug` / `enhancement`). Labels are already fetched
   (`PRS_QUERY:106`) but **discarded** — the `Task` dataclass (`:214-233`) has no
   label field. Retain them.
2. **Conventional-commit prefix** of the title. `CONVENTIONAL_RE` already exists
   (`:175-177`) but is used only for AI stylometry (`:199`). Reuse it.
3. **`plan_file` `#bug` marker** — `PLAN_BUG_RE` (`:717`) already parses this.

Measured coverage of step 2 alone on current data: `fix` 591, `feat` 362,
`refactor` 186, `chore` 48, `style` 43, `docs` 18, `perf` 8, `revert` 5, `test` 1,
`build` 1, none 765 → **~62% classified for free.**

Explicit prefix mapping (no other prefix implies a category):

| Prefix | `work_type` |
|---|---|
| `fix`, `hotfix`, `revert`, `bugfix` | `bug` |
| `feat` | `feature` |
| `refactor`, `chore`, `docs`, `style`, `perf`, `test`, `build`, `ci` | `other` |
| no recognised prefix | `other` |

`other` is a real classification, not a failure state — refactoring and chores are
genuinely neither a bug nor a user request. Velocity calculations must therefore use
`bug` + `feature` as the denominator, not all tasks.

Backlog mapping is satisfied by `plan_file` (D3): plan tasks carry `#bug`, giving a
direct bug-vs-feature split against declared project scope.

Bump `schema_version` (`:945`).

### #3 Owner filter — Phase 1

Data already present: `Task.author` (`:226`), populated at `:515-516` (commits) and
`:603` (PRs). **16 distinct authors** across 2,028 tasks, retained per work item.

Frontend: a contributor `<select>` alongside the existing repo/branch/window filters,
feeding the same `state` + `render()` path.

Two data-layer fixes:
- **Identity aliasing.** Commit authors fall back to the git display name when no
  GitHub account resolves (`:516`), so `Shane` appears beside logins like `wing-csi`
  — the same human can appear twice. Add a `[classify.author_aliases]` config map,
  following the existing `author_levels` pattern.
- Raise `assignees(first:2)` (`:149`, `:157`) if issue-assignee filtering is wanted.

Reviewer identity is *not* retained (`PrSignals:394-406` keeps counts only).
"Tasks reviewed by X" is out of scope.

### #4 SPDT — Phase 1

Config-only, given D6. Procedure:

1. Add `[[repos]]` entries to `config.toml` (pattern at `:14-105`).
2. If separate credentials are needed: add a repo secret, one `env:` line in
   `collect.yml` (the `BEN_GH_METRICS_TOKEN` precedent at `:41`), and
   `token_env = "..."` on the repo entry. Missing env fails loudly (`:924-930`).
3. Set `sop_paths`, `branches`, `no_evidence_level` per repo as appropriate.

**Input required at implementation time:** exact `owner/repo` names. Precedent
warns against guessing — `benegg/BOCPT-GENERAL-WEB` was configured from a guessed
name that does not exist and is now commented out (`config.toml:81-88`).

### #5 Today's Tasks — Phase 0 fix + Phase 2 data

1. **Delete the dead first `issueScore` (`:763-773`) and `PRIORITY_RE`**, keeping the
   object-returning version and fixing the comparator at `:1151` to compare `.sc`.
   This alone makes the existing list sort correctly.
2. Filter to items due today, evaluated against **the viewer's local date**, not
   `generated_at` — membership is stale-tolerant, so this is safe and makes "today"
   mean today.
3. Source: `plan_file` open tasks with `due:` markers. GitHub issues with milestone
   `dueOn` are used **additively where available**, but are not relied upon — per §2.3
   they are absent for 12 of 13 repos, which is precisely why D3 chose plan files.
   The list must render correctly from plan data alone.
4. Keep the existing staleness stamp visible (`:371`, `:566`); completion state is
   still a 05:00 snapshot.

Scoring rules stay deterministic and documented in the UI, per existing design.

### #6 Project Progress — Phase 2

- **Completion %** from `plan_file` checked/total, already implemented
  (`:1057-1083`); it activates as soon as plan files exist.
- **Project start/end**: new per-repo `config.toml` keys `start_date` / `end_date`,
  plumbed through `repo_meta`. Enables elapsed-vs-completed comparison.
- **Burn-down**: new `history.json`, append-only, **aggregates only** — per repo per
  day: open/closed counts, plan done/total. Written to R2 alongside `metrics.json`.
  Aggregates-only keeps it small; embedding history in the 1.2 MB `metrics.json`
  would be the wrong shape.

**Recorded limitation:** the chart starts empty and accrues from ship day. No backfill
exists (§2.5).

### #7 Live Document Reflection — Deferred

Cannot be scoped until the hosting system is named. Cost varies by an order of
magnitude: markdown in a tracked repo is near-free (the `plan_file` / `quality_file`
fetchers at `:703-710`, `:769-777` generalize directly); a GitHub wiki needs a shallow
clone of `owner/repo.wiki.git` (not reachable via the contents API); Confluence /
Notion / Google Docs / SharePoint each need auth, an API client, content conversion,
and — for the latter two — org-admin consent.

Note also that client-side "live" fetching is only viable for **public** content: the
page is static, so any token would be exposed in source.

**Blocking questions:** which system hosts the charters; is the content private; is a
read-only mirror sufficient or must content be parsed into fields; what freshness is
genuinely required.

### #8 Rework statistics — Phase 4

Per D4, redefine to commit-level signals that this workflow actually produces:

1. **Revert detection** in the collector — `Revert "..."` / `revert:` titles.
   41 such tasks already exist and are currently invisible to the data layer.
2. **Fix-after-fix chains** — a `fix:` commit touching ≥1 path that a prior `fix:`
   commit in the same repo also touched **within the preceding 14 days**. This is the
   direct-push analogue of "sent back for rework." The 14-day window is a new
   `config.toml` key (`rework_window_days`, default 14) rather than a hardcoded
   constant, because the right value is empirical and will need tuning against real
   output. Only the *second and subsequent* fixes in a chain count as rework, so a
   one-off fix never scores.
3. **Retain rework on closed-unmerged PRs** (currently dropped at `:596-599`).
4. **Honest denominators** in the UI: where a metric covers only the 5 PRs, say so
   rather than rendering a percentage that implies full coverage.

Reopened-issue and CI-failure tracking are **explicitly out of scope** under D4 — both
depend on the Issues:Read / Checks permissions the tokens lack. Revisit if permissions
are granted.

---

## 7. Phasing

| Phase | Contents | Depends on |
|---|---|---|
| **0 — Foundations** | Fix `issueScore` duplicate; split frontend (§5.4); make `collect_issues` record permission failures in `errors` | — |
| **1 — Cheap wins** | #3 owner filter + alias map; #4 SPDT config; #2 `work_type` ladder | Phase 0 split |
| **2 — Planning data** | Adopt `plan_file`; #5 today's tasks; #6 progress + `history.json` | Teams writing plan files |
| **3 — Auth** | Worker, OAuth, collaborator check; remove `metrics.json` from repo | Cloudflare account |
| **4 — Rework** | #8 commit-level detection | Phase 1 `work_type` |
| **Deferred** | #7 | Source system named |

Phase 0 is genuinely first: §2.4 shows what happens when features are added to the
monolith without it.

**Each phase gets its own implementation plan and its own spec→plan→build cycle.**
This document is the shared design; it is deliberately too large to implement in one
pass. Phases 0 and 1 are the only ones with no external dependency, so they are the
natural first plan. Phase 2 cannot start until plan files exist in target repos, and
Phase 3 cannot start without a Cloudflare account — treating them as one plan would
block deliverable work behind other people's actions.

---

## 8. Testing

Per project convention (`scripts/test_collect_github.py`) and the global 80% coverage
rule.

- **Collector**: TDD against the existing `FakeClient` canned-GraphQL pattern with
  `pr_node` / `commit_node` builders (`:28-107`). Every new field gets a test; every
  schema addition bumps `schema_version`.
- **`work_type` ladder**: one test per rung plus precedence (label beats prefix beats
  plan marker).
- **Rework**: fixtures for revert titles, fix-after-fix chains inside and outside the
  window, and the no-double-count guarantee.
- **Worker `authorize.js`**: the security-critical unit. Pure function over an
  injected client; tests must include the **fail-closed** case on GitHub API error.
- **Frontend**: the split must be behaviour-preserving — capture current rendered
  output for a fixed `metrics.json` before refactoring and diff after.

---

## 9. Process dependencies (not code)

These are the honest blockers on value delivery:

1. **Teams must write `plan_file` markdown.** Without it #5 and #6 stay empty
   regardless of code quality. This is the single highest-leverage non-code action.
2. **SPDT repo names** must be supplied exactly.
3. **Cloudflare account** required for Phase 3.
4. Optionally, granting Issues:Read on the `benegg`/`abci` tokens would unlock
   issue-based progress and reopened-issue tracking as an alternative to plan files.
5. **The exact Chinasoft email domain** must be supplied before Phase 3 (§5.2), along
   with a GitHub OAuth App (client ID + secret, stored as Worker secrets).
6. **Per-repo `start_date` / `end_date`** for #6 need an owner — someone must know and
   maintain each project's real timeline, or the elapsed-vs-completed comparison is
   meaningless.

---

## 10. Out of scope

- Converting the frontend to immutable state updates (behaviour-preserving split only)
- Reviewer-based filtering
- Reopened-issue and CI-failure rework signals (D4)
- Requirement #7 in any form
- Purging historical `metrics.json` blobs from git history (available as a follow-up)
- Any write path / data modification feature — none exists today (§3)
