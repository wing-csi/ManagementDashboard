# Management Dashboard — 8 Feature Enhancements

**Date:** 2026-07-27
**Status:** Revision 3 — Phase 0 shipped; Phase 1 re-scoped to GitHub-only
**Analysis:** Fable 5 (3 parallel agents) · **Adversarial review:** Fable 5 · **Implementation:** Opus 5 / Sonnet 5

> Spec lives in `specs/` at repo root, **not** `docs/`. `docs/` is the GitHub Pages
> artifact root (`.github/workflows/collect.yml:48`), so anything placed there is
> published. This document describes authentication architecture and a live data
> exposure; it must not be published.

**Revision 2 changelog.** An adversarial Fable 5 review found the revision-1 design
unsound in three places. Corrected here: the authorization mechanism was undesigned
(§5.2); the claim that swapping the CI deploy step ends the exposure was **false**
(§5.3); and the rework heuristic required per-commit file paths the collector does not
fetch (§6.8). Phases were re-sequenced (§7) and a factual error in the §3 evidence
table was fixed. Details at §11.

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
red-line detection, and claim-vs-behaviour verification. The eight requirements land on
top of substantial existing machinery — in several cases on machinery that already
implements them.

---

## 2. Findings that reframe the requirements

All figures below were independently re-verified by a second agent.

### 2.1 The dataset is 99.75% direct commits

2,023 of 2,028 tasks are direct pushes; **5** are merged PRs. Every PR-derived metric
computes over a sample of five. This invalidates the naive reading of #8 and caps the
value of any PR-based signal.

### 2.2 Requirement #8 is not imprecise — it is structurally dead

`rework` counts only human `CHANGES_REQUESTED` reviews on PRs
(`scripts/collect_github.py:404`, assigned at `:638`). `collect_commits` (`:495-541`)
never sets it, so direct commits keep the dataclass default of `0`.

**Live distribution across all 2,028 tasks: `{0: 2028}`.** Not one non-zero value.

Signals the team *does* generate, currently uncollected:

- **41 revert-titled tasks** exist; the collector never flags them. Only frontend
  regexes see them (`docs/index.html:590` `FIX_RE`, `:591` `FAIL_RE`).
- **"Reopened" is never queried.** `ISSUES_QUERY` (`:140-169`) fetches neither
  `stateReason` nor `timelineItems(itemTypes:[REOPENED_EVENT])`.
- **"Failed QA" is invisible.** `_ci_state` (`:579-582`) reads `statusCheckRollup` of
  the *last commit only* — a PR that failed CI five times then passed reports `pass`.
- **Dismissed reviews vanish.** A `CHANGES_REQUESTED` later dismissed becomes
  `DISMISSED` and stops counting; rework retroactively disappears.
- **Closed-unmerged PRs drop rework entirely** (`:596-599`).

### 2.3 Requirements #5 and #6 are ~80% built but starved of data

UI exists: `今日建議優先處理` (`docs/index.html:487-504`, rendered `:1151-1154`),
milestone bars (`:1087-1096`), completion chips (`:1057-1083`).

No planning data reaches it:

- `issues` is `None` for **12 of 13 repos**.
- **Token topology** (corrected in rev. 2): the `benegg/*` repos use
  `BEN_GH_METRICS_TOKEN`; `Tony-Liu-1248/abci-crm` has **no** `token_env` and uses the
  default `GH_METRICS_TOKEN` — the same token that successfully reads issues for
  `wing-csi/AIFlowTesting`. So there is no separate "abci token": `GH_METRICS_TOKEN`
  lacks Issues:Read **on abci-crm specifically** (fine-grained per-repo permissions).
- `collect_issues` (`:780-826`) swallows failures at `:785-786`, returning `None` with
  **no entry in `errors`** — the dashboard cannot report that it is blind. The only
  error entry in the current file is the nonexistent `BOCPT-GENERAL-WEB`.
- **No repo configures `plan_file`** (`config.toml:21` commented out).

### 2.4 A live bug on the requirement #5 path

`issueScore` is declared **twice**: `docs/index.html:763-773` returns a **number** and
uses `PRIORITY_RE` (`:743-747`); `:1034-1049` returns an **object** `{sc, why}`.
Declarations hoist, so the second wins. The sort at `:1151` computes
`object - object` = `NaN`, which `SortCompare` coerces to `+0` — a stable no-op.

**The "today's suggested priorities" list renders unsorted.** The first declaration and
`PRIORITY_RE` are dead code. A textbook monolith collision: two features each added a
scorer and silently clobbered each other.

### 2.5 No history is retained — burn-down cannot be backfilled

`:955` writes a single path. The active workflow deploys `docs/` as a Pages artifact
with `contents: read` and never commits output back. Plan checkboxes carry no
completion timestamps, `closedRecent` issues cap at 30 (`:153`), milestones expose only
current counts. **No backfill is possible.**

---

## 3. Security finding (2026-07-27)

| Check | Result |
|---|---|
| `wing-csi/ManagementDashboard` visibility | **public** (anonymous API, confirmed) |
| `https://wing-csi.github.io/.../data/metrics.json` | **HTTP 200 anonymous**, 1,181,417 bytes |
| Live file `generated_at` | **2026-07-26T22:06Z** — refreshing nightly |
| Repo copy `generated_at` | 2026-07-22T18:08Z |
| `benegg/BOCPT-CMS-API`, `Tony-Liu-1248/abci-crm`, `benegg/BoostBank-ReactNative-SMEApp` | **HTTP 404 anonymous → private** (spot-check, 3 of 11) |

**2,023 of 2,028 tasks in the public file belong to private repos**, each with commit/PR
title, plus 16 author logins, branch names and issue metadata.

| Tasks | Private repo |
|---|---|
| 1,861 | `benegg/BoostBank-ReactNative-SMEApp` |
| 100 | `Tony-Liu-1248/abci-crm` |
| 25 | `benegg/BOCPT-CMS-API` |
| 24 | `benegg/BOCPT-EE-Web` |
| 7 | `benegg/BOCPT-CMS-WEB` |
| 3 | `benegg/SUNLIFE-EE-APP-ANDROID` |
| 1 each | `BOCPT-EE-APP-ANDROID`, `BOCPT-WEB-API`, `BOCPT-EE-APP-EMBED-WEB` |
| **2,023** | **total** (remaining 5 = public `wing-csi/AIFlowTesting`) |

`BOCPT-EE-APP-IOS` and `BOCPT-ORSO-API` contributed zero tasks. Privacy was
spot-checked on 3 of the 11 private repos and inferred for the rest.

Source code is not exposed; titles, authorship and branch names are. `README.md:290`
already warns *"hub public + target private = 漏緊嘢"* — the deployment violates its
own documented rule, and has continued to refresh that violation nightly.

**A client-side login would not have fixed this.** On Pages any gate is browser
JavaScript while the JSON stays fetchable at a stable URL.

### Accepted risks (explicit user decisions)

1. **Repo stays public.** Historical `metrics.json` snapshots remain readable in public
   git history (`chore: update metrics [skip ci]`, 2026-07-22); anyone who cloned or
   forked retains a copy. Flipping to private later needs no redesign.
2. **All-or-nothing authorization** (§5.2) grants a superset of GitHub's own
   permissions. Accepted knowingly; see §5.2 for the precise blast radius.

### Requirement #1's second clause rests on a wrong premise

"Prevents unauthorized data modification" — there is **no write path anywhere**. No
POST/PUT/form submission in `docs/index.html`; the workflow runs `contents: read`
(`collect.yml:11-14`). Modification is already prevented by GitHub repository
permissions. A dashboard login contributes nothing. Relay this to whoever raised it.

---

## 4. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Repo stays **public**; gate the dashboard | User decision, informed |
| D2 | **GitHub-only. No third-party services of any kind.** Auth = GitHub repo permission on a **private data repo**; no login page, no hosted URL | User constraint. Rules out Cloudflare/Workers/R2 and every external IdP (§5.2) |
| D3 | Planning source = **`plan_file` markdown** | Avoids the Issues:Read blocker; feeds #5, #6, #2 |
| D4 | Rework = **revert detection only** | Fix-after-fix needs per-commit file paths the collector does not fetch (§6.8) |
| D5 | **Split `docs/index.html`** into CSS + ES modules | 1349 lines vs. an 800 cap; §2.4 is the symptom |
| D6 | SPDT = additional GitHub repos, names supplied at implementation | Config-only |
| D7 | **Disable GitHub Pages immediately** | Stops the nightly re-publication (§5.3) |
| D8 | **Access control moves to Phase 1** | Pages going dark makes it the path back to shared, refreshed data |
| D9 | "Login with **Chinasoft email**" is **dropped, not deferred** | Impossible without a third-party IdP (D2). §5.2 |
| D10 | Phase 1 also restores **nightly refresh** via commit-back to the data repo | Phase 0 made refresh manual; that is the main day-to-day cost to undo |

---

## 5. Target architecture

### 5.1 Delivery

Collector unchanged in kind — GitHub Actions, Python, daily cron. Delivery changes.

```
  PUBLIC repo: wing-csi/ManagementDashboard
  config.toml ─▶ collect_github.py (Actions, daily) ─▶ metrics.json + history.json
                                                              │  push with DATA_REPO_PAT
                                                              ▼
  PRIVATE repo: wing-csi/ManagementDashboard-data  (data only, never code)
                                                              │  git pull
                                                              ▼
  viewer (collaborator on the private data repo) ─▶ local static server ─▶ dashboard
```

**No third-party services.** Everything above is GitHub: Actions, two GitHub repos, and
GitHub's own permission model. No Cloudflare, no external identity provider, nothing to
sign up for.

### 5.2 Access control (D2, revised)

**There is no login page, and no authenticated URL.** This is a hard platform limit,
not a preference: on the free/Pro plan a private repo's GitHub Pages site is still
publicly reachable, and access-controlled Pages exists only on GitHub Enterprise Cloud
(`README.md:283` documented this before this project began). GitHub offers no native
way to put authentication in front of a static site. Every solution that yields an
authenticated URL requires a third party, which D2 excludes.

**Therefore authentication IS GitHub repository permission.** To obtain the data you
must be able to `git pull` the private data repo, which requires GitHub credentials and
an access grant. The gate is real and server-side — it is GitHub's own auth — it simply
sits at `git pull` rather than at a web login.

| Property | Outcome |
|---|---|
| Who can read the data | Collaborators on `ManagementDashboard-data` (plus org owners) |
| How access is granted | Add a collaborator on that repo |
| How access is revoked | Remove them — effective immediately for future pulls |
| What a revoked user keeps | Whatever they already pulled. Unavoidable in any pull-based model |
| Link for non-technical stakeholders | **None.** See §5.5 |

**Why a separate data repo rather than making the hub private.** It preserves the
decision to keep the code public (D1) while still closing the exposure: code stays
open, data becomes permission-gated. It also confines the private surface to a repo
containing nothing but generated JSON, so over-sharing it leaks metrics rather than
source.

**Consequence to flag at review time:** adding SPDT repos (#4) to `config.toml` puts
their metadata into the same data repo, visible to every existing data-repo
collaborator. That is an access-scope change wearing the costume of a config change.
There is no per-repo filtering in this model — everyone with access sees every tracked
repo.

**Dropped: "login with Chinasoft email."** GitHub has no concept of email-domain
identity, so this is unachievable without a third-party IdP (Entra ID, Google
Workspace, or an auth proxy) — all excluded by D2. Recorded as dropped, not deferred.

### 5.3 Ending the exposure (corrected)

Revision 1 claimed that replacing the CI deploy step closes the exposure. **That is
false.** GitHub Pages keeps serving the last-deployed artifact indefinitely; removing
the deploy step merely stops updating it. The exposure must be ended explicitly:

**Phase 0, immediately:**

1. **Disable GitHub Pages** in repo settings (Settings → Pages → source: None). This,
   not the workflow edit, is what takes the URL down.
2. Remove the `configure-pages` / `upload-pages-artifact` / `deploy-pages` steps from
   `collect.yml` and drop the `pages`/`id-token` permissions.
3. `git rm --cached docs/data/metrics.json`; add `docs/data/metrics.json` to
   `.gitignore` so it is never re-committed to the public repo.

**Interim viewing (until Phase 1 ships).** The dashboard is dark. Anyone
needing it runs the collector locally with their own token and serves `docs/`:

```bash
export GH_METRICS_TOKEN=...
python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
python3 -m http.server -d docs 8000
```

The scheduled workflow keeps running tests and collection (catching collector breakage)
but publishes nothing. This is why auth is now Phase 1 (D8).

**Not addressed here:** historical `metrics.json` blobs already in public git history.
Purging them is a separate follow-up (§10).

### 5.4 Frontend restructure (D5)

`index.html` keeps only the skeleton. Line counts below are *targets*, not derived from
current anchor sizes:

| File | Contents | Target |
|---|---|---|
| `docs/css/dashboard.css` | the inline `<style>` (`:8-351`) | ~350 |
| `docs/js/data.js` | fetch + window/repo/branch/contributor filter state | ~150 |
| `docs/js/aggregate.js` | KPIs, weekly buckets, DORA proxies (`:620-773`) | ~200 |
| `docs/js/render-kpi.js` | KPI row, spectrum strip, alerts | ~250 |
| `docs/js/render-project.js` | progress, milestones, today's tasks | ~300 |
| `docs/js/render-table.js` | task table, sorting | ~200 |
| `docs/data/demo-data.js` | the 80,526-byte inline `DEMO_DATA` blob (`:576`) | 1 |

**Trade-off:** ES modules do not run over `file://`; local preview requires
`python3 -m http.server -d docs 8000`. Accepted.

`state` (`:604`) is a mutable singleton and `render()` (`:1282-1298`) rebuilds all
sections wholesale. The split does **not** change this — converting to immutable state
updates is out of scope, to keep the refactor behaviour-preserving.

**DEMO_DATA must stop being a silent fallback.** `loadData()` (`:610-618`) currently
substitutes the demo blob on *any* fetch failure, flagged only by a small badge. Once
auth exists, an expired session would render a plausible fake dashboard to a manager.
Required change: demo data loads **only** when explicitly requested (`?demo=1`); a
`401` triggers a login redirect; any other failure shows an explicit error state.

---

## 6. Per-requirement design

### #1 Authorization — Phase 1

Per §5.2, **no login page is built.** Access control is GitHub repository permission on
a private data repo. Deliverables:

1. **Create `wing-csi/ManagementDashboard-data`, private.** Contains only generated
   JSON — never code, never config.
2. **A fine-grained PAT** with *Contents: write* on that repo **only**, stored in the
   public repo as the secret `DATA_REPO_PAT`. Least privilege: it can write the data
   repo and nothing else.
3. **Extend `.github/workflows/collect.yml`**: after the collect step, write
   `metrics.json` (and `history.json`, per #6) into a checkout of the data repo and
   push. Guard with `if: github.event_name != 'pull_request'` so forks and PRs never
   attempt a push with a secret they cannot read.
4. **A `docs/data/.gitignore`-aware local wiring step** so a viewer can point the
   dashboard at their pulled copy — simplest is a documented `cp`/symlink from the data
   repo clone into `docs/data/metrics.json`, which is already gitignored in the public
   repo.
5. **README rewrite** of the run instructions: clone both repos, pull, serve. Replaces
   the interim "run the collector yourself" flow (§5.3).

**Testing.** There is no `authorize.js` to unit-test — the authorization logic is
GitHub's. What must be verified instead is that the pipeline cannot leak:

- a test asserting the workflow's push step is guarded and targets the data repo, not
  `origin`;
- a check that `docs/data/metrics.json` remains gitignored in the public repo after
  Phase 1 (regression guard against re-introducing the original leak);
- a manual, documented verification that the data repo is private and that a logged-out
  request for its raw content returns 404.

**Explicitly not built:** OAuth flow, session cookies, a Worker, `wrangler.toml`, R2, or
any Chinasoft-email rule (D9).

### #2 Fix / User Request — Phase 2

New `Task` field `work_type: "bug" | "feature" | "other"`, set by a two-rung ladder:

1. **PR label** (`bug` / `enhancement`). Labels are already fetched (`PRS_QUERY:106`)
   but discarded — the `Task` dataclass (`:214-233`) has no label field. Retain them.
2. **Title prefix**, via a **new `WORK_TYPE_RE`** — *not* `CONVENTIONAL_RE` (`:175-177`).
   Revision 1 said to reuse it; that regex requires a trailing colon and does not know
   `hotfix`/`bugfix`, so it would classify only the 5 `revert:` titles and miss the 36
   GitHub-style `Revert "..."` titles that #8 counts as rework — a direct contradiction
   between #2 and #8. `WORK_TYPE_RE` must match `Revert "..."` as well as `revert:`.

| Prefix | `work_type` |
|---|---|
| `fix`, `hotfix`, `bugfix`, `revert`, `Revert "…"` | `bug` |
| `feat` | `feature` |
| `refactor`, `chore`, `docs`, `style`, `perf`, `test`, `build`, `ci` | `other` |
| unrecognised | `other` |

Measured prefix coverage on current data: `fix` 591, `feat` 362, `refactor` 186,
`chore` 48, `style` 43, `docs` 18, `perf` 8, `revert` 5, `test` 1, `build` 1, none 765
→ **62.3% classified with no new API calls.**

`other` is a real category, not a failure state — refactors and chores are neither bug
nor user request. **Velocity must therefore use `bug` + `feature` as its denominator,
not all tasks.**

**A plan-file rung was specced in revision 1 and is removed.** `#bug` markers
(`PLAN_BUG_RE:717`) classify *plan checkboxes*, whereas `work_type` is a field on
`Task` (commits/PRs). No linkage between a plan line and a commit exists or is
proposed, so that rung could never fire. Plan-level bug/feature counts are a separate,
plan-scoped statistic — worth having, but not part of `work_type`.

Bump `schema_version` (`:945`).

### #3 Owner filter — Phase 2

Data already present: `Task.author` (`:226`), populated at `:515-516` (commits) and
`:603` (PRs). **16 distinct authors**, retained per work item.

Frontend: a contributor `<select>` beside the existing repo/branch/window filters,
feeding the same `state` + `render()` path.

Data-layer fixes:

- **Identity aliasing.** Commit authors fall back to the git display name when no
  GitHub account resolves (`:516`) — `Shane` sits beside logins like `wing-csi`, so one
  human can appear twice. Add `[classify.author_aliases]`, following the existing
  `author_levels` pattern.
- Raise `assignees(first:2)` (`:149`, `:157`) if issue-assignee filtering is wanted.

Reviewer identity is not retained (`extract_signals:394-406` keeps counts only; the
`PrSignals` dataclass is at `:360-374`). "Tasks reviewed by X" is out of scope.

### #4 SPDT — Phase 2

Config-only. Procedure:

1. Add `[[repos]]` entries to `config.toml` (pattern at `:14-105`).
2. If separate credentials are needed: add a repo secret, one `env:` line in
   `collect.yml` (the `BEN_GH_METRICS_TOKEN` precedent, `:41`), and `token_env` on the
   repo entry. Missing env fails loudly (`:924-930`).
3. Set `sop_paths`, `branches`, `no_evidence_level` per repo.
4. **Review who this newly exposes.** SPDT metadata lands in the same private data
   repo, so every existing data-repo collaborator gains visibility of it (§5.2).

**Input required:** exact `owner/repo` names. Precedent warns against guessing —
`benegg/BOCPT-GENERAL-WEB` was configured from a guessed name that does not exist
(`config.toml:81-88`).

### #5 Today's Tasks — Phase 0 fix + Phase 3 data

1. **Delete the dead first `issueScore` (`:763-773`) and `PRIORITY_RE`**, keep the
   object-returning version, fix the comparator at `:1151` to compare `.sc`. This alone
   makes the existing list sort correctly — a Phase 0 one-liner.
2. Filter to items due today against **the viewer's local date**, not `generated_at`.
3. Source: `plan_file` open tasks with `due:` markers. Issues with milestone `dueOn`
   are additive **where available** — per §2.3 they are absent for 12 of 13 repos, so
   the list must render correctly from plan data alone.
4. Keep the staleness stamp visible (`:371`, `:566`); completion state remains a
   05:00 snapshot.

### #6 Project Progress — Phase 3

- **Completion %** from `plan_file` checked/total, already implemented (`:1057-1083`);
  activates as soon as plan files exist.
- **Project start/end**: new per-repo `config.toml` keys `start_date` / `end_date`
  (`YYYY-MM-DD`), plumbed through `repo_meta`.
- **Burn-down** via a new `history.json`: append-only, **aggregates only** — per repo
  per day, open/closed counts and plan done/total. Stored in the **private data repo**
  beside `metrics.json` (revision 3: was Cloudflare R2).

**Read-back design:** because the workflow already checks out the data repo to push
(#1), history read-back is just reading the file from that checkout. The collector
appends today's aggregate row, replacing any row with the same date so re-runs are
idempotent, then the existing push step commits it. A missing file means first run →
start a new one. **No new credentials** — it reuses `DATA_REPO_PAT`.

Git also gives history-of-the-history for free: if an aggregate is ever computed wrong,
the data repo's commit log shows exactly when it changed.

**Recorded limitation:** the chart accrues from ship day; no backfill exists (§2.5).

### #7 Live Document Reflection — Deferred

Unscopeable until the hosting system is named. Costs differ by an order of magnitude:
markdown in a tracked repo is near-free (the `plan_file`/`quality_file` fetchers at
`:703-710`, `:769-777` generalize directly); a GitHub wiki needs a shallow clone of
`owner/repo.wiki.git` (not reachable via the contents API); Confluence / Notion /
Google Docs / SharePoint each need auth, an API client and content conversion, with the
latter two requiring org-admin consent.

Client-side "live" fetching is viable only for **public** content — the page is static,
so any token would be exposed in source.

**Blocking questions:** which system hosts the charters; is the content private; mirror
or parsed-into-fields; what freshness is genuinely required.

### #8 Rework statistics — Phase 4

Per D4, **revert detection only**.

Revision 1 specced fix-after-fix chains over shared file paths. Verified: `COMMITS_QUERY`
(`:75-93`) fetches `additions deletions` but **no file paths**, and the GraphQL `Commit`
type does not expose a changed-file list. Only `PRS_QUERY:109` has
`files(first:100){ path changeType }`, covering the 5 PRs. Implementing it would require
~600 REST calls per run for the 591 fix commits, plus a high-churn path denylist —
otherwise lockfiles and route files chain endlessly and the metric gets dismissed as
noise. Descoped.

Scope now:

1. **Revert detection** in the collector — a `is_revert` flag from `Revert "..."` /
   `revert:` titles. 41 such tasks already exist and are invisible to the data layer.
   Uses data already fetched; no new API calls.
2. **Honest denominators** in the UI: where a metric covers only the 5 PRs, say so
   rather than rendering a percentage implying full coverage.

Explicitly out of scope: fix-after-fix chains, reopened-issue tracking, CI-failure
counts, and retaining rework on closed-unmerged PRs (which today are not `Task` records
at all — `:596-599` keeps only a date, so this needs a new record type).

---

## 7. Phasing

| Phase | Contents | Depends on | Status |
|---|---|---|---|
| **0 — Contain & stabilise** | Strip deploy steps; gitignore `metrics.json`; fix duplicate `issueScore`; split frontend (§5.4); `collect_issues` records failures; stop silent DEMO fallback | — | ✅ **done** (`106bb63`..`10839bf`, 85 tests). ⚠️ Manual Pages disable still outstanding |
| **1 — Private data repo** | Create the private data repo; `DATA_REPO_PAT`; nightly commit-back; README rewrite. Restores automatic refresh and gates the data behind GitHub permissions | Data repo + PAT (§9.3) | next |
| **2 — Cheap wins** | #3 owner filter + alias map; #4 SPDT; #2 `work_type` | Phase 0 split | |
| **3 — Planning data** | Adopt `plan_file`; #5 today's tasks; #6 progress + `history.json` | Teams writing plan files; data repo from Phase 1 | |
| **4 — Rework** | #8 revert detection + honest denominators | Phase 2 `work_type` | |
| **Deferred** | #7 | Source system named | |

**Each phase gets its own implementation plan and its own spec→plan→build cycle.** This
document is the shared design; it is deliberately too large for one pass.

**Rollback.** Phase 1 is low-risk to reverse: delete the push step and the data repo.
The local-collector path (§5.3) keeps working throughout, so a broken push step
degrades to "run the collector yourself", never to "no dashboard". No deploy, no DNS,
no external service to roll back.

**Local development after Phase 1.** Two supported paths, both offline-capable: pull
the data repo, or run the collector directly with your own token. The frontend always
reads `./data/metrics.json` — how that file arrives is the viewer's choice.

---

## 8. Testing

Per project convention (`scripts/test_collect_github.py`) and the global 80% rule.

- **Collector**: TDD against the existing `FakeClient` canned-GraphQL pattern with
  `pr_node`/`commit_node` builders (`:28-107`). Every new field gets a test; every
  schema addition bumps `schema_version`.
- **`work_type`**: one test per rung, plus precedence (label beats prefix), plus the
  `Revert "..."`-vs-`revert:` case that revision 1 got wrong.
- **Revert detection**: fixtures for both revert title forms and the no-double-count
  guarantee.
- **`authorize.js`**: the security-critical unit — pure function over an injected
  client. Must include fail-closed on API error and the `evil-chinasoft.com` near-miss.
- **`history.json`**: first-run (missing object), append, and same-date idempotent
  re-run.
- **Frontend**: the split must be behaviour-preserving — capture rendered output for a
  fixed `metrics.json` before refactoring and diff after.

---

## 9. Process dependencies (not code)

1. **Teams must write `plan_file` markdown.** Without it #5 and #6 stay empty
   regardless of code quality. Highest-leverage non-code action.
2. **SPDT repo names**, exactly.
3. **Create the private data repo** `ManagementDashboard-data` and mint a fine-grained
   PAT scoped to *Contents: write on that repo only*, stored as `DATA_REPO_PAT`. Gates
   Phase 1. No third-party account needed.
4. **Decide who gets data-repo access**, and accept that everyone on that list sees
   every tracked repo's metadata (§5.2 — no per-repo filtering).
5. **Disable GitHub Pages** — still outstanding, and it is what actually closes the
   original exposure.
6. **Per-repo `start_date` / `end_date`** need an owner who knows each project's real
   timeline, or the elapsed-vs-completed comparison is meaningless.
7. Optionally, granting Issues:Read (on `BEN_GH_METRICS_TOKEN` for benegg repos, and on
   `GH_METRICS_TOKEN` for abci-crm) would unlock issue-based progress as an alternative
   to plan files.

---

## 10. Out of scope

- Converting the frontend to immutable state updates (behaviour-preserving split only)
- Per-repo data filtering per viewer (the upgrade path for §5.2's accepted blast radius)
- Reviewer-based filtering
- Fix-after-fix chains, reopened-issue and CI-failure rework signals (D4)
- Requirement #7 in any form
- Purging historical `metrics.json` blobs from public git history — available as a
  follow-up at any time
- Any write path / data modification feature — none exists today (§3)

---

## 11. Revision 3 changes (2026-07-27, post-Phase-0)

User constraint: **"only work in github, i dont want any third party things."**

| Area | Was (rev. 2) | Now (rev. 3) |
|---|---|---|
| Hosting | Cloudflare Pages/Workers + R2 | **None.** Local viewing only |
| Auth | GitHub App + OAuth + collaborator check in a Worker | **GitHub repo permission** on a private data repo. No login page |
| Chinasoft email login | Supported via verified-email rule | **Dropped** — impossible without a third-party IdP (D9) |
| `history.json` store | Cloudflare R2 | Private data repo; reuses `DATA_REPO_PAT`, no new credentials |
| Phase 1 name | "Auth & hosting" | "Private data repo" |
| Refresh model | Nightly to R2, served by Worker | Nightly commit-back; viewers `git pull` |

**What this costs, stated plainly (§5.5):** no shareable URL, no always-on dashboard,
no per-viewer filtering. Every viewer needs a GitHub account, data-repo access, git,
Python and a terminal. Non-technical stakeholders cannot be served by this model. The
only routes that would change that are GitHub Enterprise Cloud or a third-party host,
both currently excluded.

**What it gains:** zero new vendors, zero cost, no secrets at a public edge, no OAuth
code to write or get wrong, and the exposure closes permanently rather than being
gated. It also restores nightly refresh, undoing Phase 0's main day-to-day cost.

---

## 12. Revision 2 corrections

| ID | Severity | Correction |
|---|---|---|
| D1 | CRITICAL | §5.2 authorization mechanism was undesigned. Now a GitHub App installation token; visitors grant only `read:user`, never `repo` |
| D3 | HIGH | §5.3's "closes the exposure" claim was **false** — Pages keeps serving the last artifact. Explicit Pages disablement added to Phase 0 |
| D4 | HIGH | §6.8 fix-after-fix needed per-commit file paths the collector does not fetch. Descoped to revert detection |
| D5 | HIGH | history.json (Phase 2) wrote to R2 (Phase 3). Phases re-sequenced; read-back designed |
| D2 | HIGH | All-or-nothing blast radius now stated explicitly as an accepted risk, not hidden behind "auto-syncs with repo access" |
| D6 | MEDIUM | §5.2/§5.3 described two different topologies. Resolved to single-origin; cookie attributes and OAuth `state` specified |
| D7 | MEDIUM | Silent DEMO_DATA fallback becomes a post-auth trap. Now explicit-only, with 401 → login redirect |
| D8 | MEDIUM | #2 mapping table could not be produced by `CONVENTIONAL_RE`; new `WORK_TYPE_RE`. Unreachable plan-marker rung removed |
| D9 | MEDIUM | Worker allowlist sync specified; SPDT-expands-access flagged |
| D10 | MEDIUM | Rollback plan and post-cutover local-dev story added |
| F1 | MEDIUM | §3 breakdown said "62 across six repos"; actually **13 across five**, and the table summed to 2,072 against a correct headline of 2,023. Corrected with per-repo figures |
| F2 | LOW | "the abci token" does not exist — abci-crm uses the default `GH_METRICS_TOKEN` |
| F3 | LOW | "verified first-hand" overstated: 3 of 11 private repos spot-checked, rest inferred |
| F4 | LOW | `PrSignals` dataclass is `:360-374`; `FIX_RE:590` also matches reverts; §5.4 sizes relabelled as targets |
| D11 | LOW | Dead plan-marker rung removed from Phase 2 |
