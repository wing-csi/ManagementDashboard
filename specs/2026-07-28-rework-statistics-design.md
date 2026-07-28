# Rework Statistics — Correction & Extension — Design

**Date:** 2026-07-28
**Status:** Approved, not yet implemented
**Scope:** `scripts/collect_github.py`, `docs/js/aggregate.js`, `docs/js/render-kpi.js`, `docs/js/render-table.js`, `docs/index.html`, `docs/css/dashboard.css`, `README.md`, fixtures

> Spec lives in `specs/` at repo root, **not** `docs/`. `docs/` is the published
> artifact root — anything placed there ships to Cloudflare Pages.

---

## 1. Problem

「PR 打回率」 is the dashboard's only direct, un-inferred quality signal — the
README says so explicitly ([README.md:90](../README.md), 「直接嚟自 GitHub review
記錄,冇得靠估」). It is also wrong in several ways, and what it needs is a
definition change, not a patch.

Today `rework` is the count of human `CHANGES_REQUESTED` reviews on a **merged**
PR ([collect_github.py:638](../scripts/collect_github.py)), and the rate is
`reworkPRs / prTotal` ([aggregate.js:49](../docs/js/aggregate.js),
[render-kpi.js:242](../docs/js/render-kpi.js)).

### 1.1 Confirmed defects

| # | Defect | Where | Effect on the number |
|---|---|---|---|
| 1 | Denominator counts PRs nobody reviewed | [aggregate.js:48](../docs/js/aggregate.js) | Structurally **deflated**. Auto-merged agent PRs and `merged-without-review` violations cannot be rejected, yet they sit in the denominator as if they had passed review |
| 2 | Rejected-then-abandoned PRs are invisible | [collect_github.py:596](../scripts/collect_github.py) | The strongest rework signal contributes nothing. Non-merged PRs are skipped; only their close date reaches `closed_unmerged`, with no author |
| 3 | Dismissed rejections vanish | [collect_github.py:404](../scripts/collect_github.py) | **Undercount.** GitHub rewrites `state` to `DISMISSED` when a rejection is dismissed, so it stops matching `CHANGES_REQUESTED` — the overridden-gate case a manager most wants to see |
| 4 | Reviews capped at 50, unpaginated | [collect_github.py:104](../scripts/collect_github.py) | **Silent undercount.** `COMMENTED` reviews consume the budget on chatty PRs |
| 5 | Events counted, not rounds | [collect_github.py:404](../scripts/collect_github.py) | **Inflated per-PR.** Two reviewers rejecting one push reads as 2. [test_collect_github.py:329](../scripts/test_collect_github.py) asserts this behaviour — that assertion *is* the defect |
| 6 | 接受率 mixes person and repo scope | [render-kpi.js:248](../docs/js/render-kpi.js) | Person-filtered `prTotal` ÷ repo-wide `meta.closedUnmerged`. Under a person filter, one person's merges are divided by the whole repo's rejections |
| 7 | Self-review counts as a review | [collect_github.py:394-397](../scripts/collect_github.py) | Review authors are filtered by `_is_bot` only, never against the PR's own author. GitHub blocks self-approve and self-request-changes but permits a `COMMENTED` self-review |
| 8 | 接受率 filters bots asymmetrically | [collect_github.py:596-604](../scripts/collect_github.py) | `exclude_authors` is applied *after* the non-merged `continue`, so excluded authors' merged PRs are dropped while their closed PRs still inflate `closed_unmerged` |

Defect 6 and 8 live in the adjacent 接受率 card rather than in rework itself, but
both sit inside code this change already edits — 6 in the same `renderQuality()`
block, 8 in the same `collect_prs()` loop. Both are in scope.

### 1.2 Why defect 7 is load-bearing

Defect 7 is the one defect that the fix for defect 1 would otherwise make worse.
The new denominator is "PRs that received a human review", so a self-`COMMENTED`
review would mark a PR `reviewed = true` and put it back in the denominator
despite no outside reviewer ever having looked — re-creating defect 1 through a
side door.

It also has a live governance consequence, independent of this change:
`merged-without-review` ([collect_github.py:561](../scripts/collect_github.py))
tests `s.human_reviews == 0`, so a self-comment silently suppresses that red
line. Today a developer can dodge the check by commenting on their own PR.

The fix is one predicate — exclude reviews whose author equals the PR author when
computing `human_reviews` / `reviewed`. Rejections are unaffected, since
self-rejection is impossible on GitHub.

### 1.3 Decisions taken

| Question | Decision | Consequence |
|---|---|---|
| What does 打回率 measure? | 被打回 ÷ **有人 review 過**嘅 PR | Fixes 1, 3, 4, 5, 7. The published rate goes **up** — it stops crediting un-reviewed auto-merges as "not rejected" |
| What is a "round"? | Rejections separated by a **new push** | Uses only GitHub-recorded facts; no tuning constant |
| New statistics | 返工周轉時間 + 平均返工輪數 | Both derive from review `submittedAt`; one collector change serves both |
| Defect 2 (abandoned PRs) | **Out of scope** | Would require collecting non-merged PRs as first-class rows. Recorded in §7 |

## 2. Definitions after this change

| Metric | Formula | Notes |
|---|---|---|
| **PR 打回率** | PRs with ≥1 **pre-merge** rejection ÷ PRs with ≥1 **outside** human review × 100 | Denominator excludes PRs with no human review, and self-reviews do not qualify |
| **平均返工輪數** | median rounds over rejected PRs | Shown as sub-text on the 打回率 card, not its own card |
| **返工周轉時間** | median hours, first rejection → `mergedAt` | New KPI card. Measures the whole rework period, not just the last round |
| **`↩N` badge** | rework **rounds** on that PR | Meaning changes from events to rounds |

A **rejection** is a human `CHANGES_REQUESTED` review, whether still live or since
dismissed, **submitted before the PR merged**. GitHub permits reviewing an
already-merged PR, but a rejection arriving after the merge caused no rework —
the code had already shipped — so it counts as neither a round nor turnaround
time. A **round** is a maximal run of rejections with no push between them.

## 3. Collector — `scripts/collect_github.py`

### 3.1 Query

Four additive changes to `PRS_QUERY`:

```graphql
reviews(first:50){ totalCount nodes{ state author{ login __typename } } }
rejections: reviews(first:50, states:[CHANGES_REQUESTED]){
  nodes{ author{ login __typename } submittedAt } }
timelineItems(first:20, itemTypes:[REVIEW_DISMISSED_EVENT]){
  nodes{ ... on ReviewDismissedEvent {
    previousReviewState
    dismissedReview{ submittedAt author{ login __typename } } } } }
commits(first:50){ nodes{ commit{ message committedDate } } }
```

`dismissedReview.submittedAt` is used rather than the event's own `createdAt`:
round detection needs when the rejection was *made*, not when it was waved away.

**Defect 4 dissolves rather than being patched.** Splitting the connection means
rejections no longer compete with `COMMENTED` noise for 50 slots, and `reviewed`
is a zero/non-zero test — truncation at 50 cannot turn "≥1 review" into "0". The
one residual is `approvals < 2` in the `core-without-double-review` check, which
is pre-existing, unrelated to rework, and left alone (§7).

### 3.2 `PrSignals`

Gains `rejections: tuple[str, ...]` — submit timestamps of every human rejection,
live and dismissed (`previousReviewState == "CHANGES_REQUESTED"`), sorted
ascending. `changes_requested` becomes `len(rejections)`.

That redefinition also reaches `infer_level` and `verify_claim`, which both test
`changes_requested > 0` as evidence of a human gate. Counting dismissed
rejections there is a strict improvement — a dismissed rejection is still a gate
that happened — and neither signature changes.

`human_reviews` changes in two ways, both from §1.2:

- excludes `PENDING` (unsubmitted drafts)
- excludes reviews whose author is the PR author (defect 7)

`extract_signals` therefore needs the PR author login, which it can read from the
node it already receives — no signature change.

### 3.3 New pure function

```python
def rework_rounds(rejections: Sequence[str], pushes: Sequence[str]) -> int:
    """A round = a run of rejections with no push between them."""
```

`rounds = 1 + count of rejections having ≥1 push strictly between themselves and
the previous rejection`; `0` when `rejections` is empty. Both inputs are ISO-8601
strings, sortable lexicographically. No I/O — directly unit-testable.

Known imprecision: a force-push rewrites `committedDate`, so a rebase with no
functional change can register as a round boundary. This over-counts in the
honest direction — it never hides rework — and needs no GitHub data we lack.

### 3.4 `Task`

| Field | Type | Meaning |
|---|---|---|
| `reviewed` | `bool` | ≥1 human review by someone other than the author, any state except `PENDING` |
| `rework` | `int` | **Redefined**: rounds, was events |
| `rework_hours` | `float \| None` | First rejection → `mergedAt`, rounded to 1dp like `lead_hours` |

`rework_hours` is `None` when there are no rejections.

### 3.5 Defect 8 — author filter ordering

In `collect_prs()`, the `exclude_authors` check ([line 604](../scripts/collect_github.py))
moves **above** the non-merged branch at [line 596](../scripts/collect_github.py),
so an excluded author's PR is skipped whether it merged or not.

Default `exclude_authors` is `["dependabot[bot]", "renovate[bot]",
"github-actions[bot]"]` ([config.toml:149](../config.toml)), and dependabot PRs
are closed and superseded constantly — every one currently deflates 接受率.
[README.md:402](../README.md) already promises 「完全唔計呢啲 author」, so this
aligns the code with its documented contract rather than changing the contract.

## 4. Aggregation — `docs/js/aggregate.js`

```js
reviewedPRs: 0, reworkPRs: 0, reworkRounds: [], reworkTurnarounds: [],
```

Inside the `t.kind === 'pr'` branch:

```js
if (t.reviewed) s.reviewedPRs++;
if ((t.rework || 0) > 0) {
  s.reworkPRs++;
  s.reworkRounds.push(t.rework);
  if (t.rework_hours != null) s.reworkTurnarounds.push(t.rework_hours);
}
```

Invariant, and a test: `reworkPRs <= reviewedPRs` always — a rejection implies a
review.

Both new metrics are task-derived, so they re-scope correctly under the person
filter with no extra work. This is exactly why defect 6 does not recur here:
`closed_unmerged` is repo-level metadata, `rework_hours` is not.

## 5. Presentation

### 5.1 `docs/js/render-kpi.js`

**打回率 card** — `pct(cur.reworkPRs, cur.reviewedPRs)`.

| State | Value | Sub-text |
|---|---|---|
| `reviewedPRs > 0` | the rate | `N / M 個有 review 嘅 PR 被打回 · 中位 R 輪` |
| `reviewedPRs === 0`, `prTotal > 0` | `–` | 「此範圍內無經 review 嘅 PR」 |
| `prTotal === 0` | `–` | 「此範圍內無 PR」 |

Today's single 「無 PR」 message conflates the middle and bottom rows. A repo that
merges everything unreviewed is a finding, not an absence of data, and it now
reads differently from a repo with no PR flow at all.

**返工周轉時間 card** (new) — `fmtHours(median(cur.reworkTurnarounds))`, sub-text
「由第一次打回到 merge · N 個 PR」, `–` when the list is empty.

**接受率 card** (defect 6) — when `state.person !== 'all'`, render `–` with a
`.scope-note` explaining it needs repo-wide scope, matching the 變更失敗率
treatment at [render-kpi.js:188](../docs/js/render-kpi.js).

### 5.2 `docs/index.html`, `docs/css/dashboard.css`

Fifth `.kpi` block in `.qgrid`; the `.qgrid` desktop rule goes `repeat(4, 1fr)` →
`repeat(5, 1fr)` ([dashboard.css:302](../docs/css/dashboard.css)). The mobile
`repeat(2, 1fr)` override at line 332 already handles the wrap. The section's
`card-note` gains the rounds distinction.

### 5.3 `docs/js/render-table.js`

`↩N` badge tooltip 「被打回 N 次」 → 「被打回 N 輪」
([render-table.js:138](../docs/js/render-table.js)).

## 6. Tests, fixtures, docs

### 6.1 Tests — TDD, red first

`scripts/test_collect_github.py`:

| Test | Asserts |
|---|---|
| Two reviewers, same push | `rework == 1` — **rewrites** the `== 2` assertion at [test_collect_github.py:329](../scripts/test_collect_github.py) |
| Reject → push → reject | `rework == 2` |
| Dismissed rejection | Counted; `changes_requested` includes it |
| Zero human reviews | `reviewed is False`; ≥1 outside review → `True` |
| Author's own `COMMENTED` review only | `reviewed is False` (defect 7) and `merged-without-review` still fires |
| `rework_hours` | Measured from the **first** rejection to `mergedAt` |
| No rejections | `rework == 0` and `rework_hours is None` |
| Excluded author, closed unmerged | Absent from `closed_unmerged` (defect 8) |

`rework_rounds()` gets direct unit tests for the empty, single, and interleaved
cases without going through a PR node.

Frontend: an aggregation test that `reworkPRs <= reviewedPRs`, and that the 打回率
card reads `–` with the un-reviewed message when every PR is unreviewed.

### 6.2 Baseline — verified unaffected

An earlier draft of this spec claimed `rendered-baseline.json` would shift. It
will not, and the reason matters for the plan:

- `SECTION_IDS` in [test_frontend_snapshot.py:29-32](../scripts/test_frontend_snapshot.py)
  captures `strip`, `alertList`, `taskRows`, `projChips`, `projMilestones`,
  `projLate`, `projTodo`, `footStamp`. The `.qgrid` quality block is **not**
  among them, so 打回率 and the new card are outside the snapshot entirely.
- `taskRows` **is** captured and does render the `↩N` badge — but
  `metrics-fixture.json` holds exactly two tasks, both `"rework": 0`, so no badge
  is emitted and the tooltip rewording changes nothing.

`metrics-fixture.json` and `rendered-baseline.json` are therefore **left
untouched**, honouring the standing rule from
[plans/2026-07-28-owner-contributor-filter.md:722-724](../plans/2026-07-28-owner-contributor-filter.md):
their whole value is proving the *default* render did not shift.

### 6.3 Fixtures

New frontend coverage gets its own fixture and module, following the precedent
of `metrics-fixture-people.json` + `test_frontend_people.py`:

- **Create** `scripts/fixtures/metrics-fixture-rework.json` — PRs covering
  reviewed/un-reviewed, single-round and multi-round rejection, so both the new
  denominator and the median have something to chew on.
- **Create** `scripts/test_frontend_rework.py`, serving that fixture by
  **intercepting the `metrics.json` request** (`page.route`), never by swapping
  the file on disk. [test_frontend_people.py:5-9](../scripts/test_frontend_people.py)
  documents why: `docs/data/metrics.json` holds the operator's real ~1.2 MB
  private data, and an interrupted disk-swap run leaves a 2 KB fixture in its
  place, which the next run then "restores" as if it were the original.

`docs/data/demo-data.js` also gains the fields. It is a hand-extracted 80 KB
single-line blob with no generator, so it is transformed by a one-off script
rather than edited by hand. Demo values are synthetic and that is legitimate:
demo mode is opt-in behind `?demo=1` and sets `state.demo = true`
([data.js:44-51](../docs/js/data.js)).

Field shapes, using synthetic values:

```json
{ "kind": "pr", "date": "2026-07-20", "lead_hours": 3.5,
  "reviewed": true, "rework": 2, "rework_hours": 18.5 }
```

Dates stay ISO-8601 `YYYY-MM-DD`; GitHub timestamps arrive as
`2026-07-20T09:14:00Z` and are sliced with `[:10]`, unchanged by this work.

### 6.4 README

Four places state these definitions and all four must move together:

| Lines | Content |
|---|---|
| ~89-93 | 品質指標 formula table |
| ~154 | `↩N` badge legend |
| ~255-263 | 品質 × 自動化 section + attribution caveat |
| ~302-307 | DORA-adjacent metric table |

The 「直接嚟自 GitHub review 記錄,冇得靠估」 claim at line 90 survives this change
and gets stronger: rounds, dismissals, and review authorship are all
GitHub-recorded facts.

## 7. Out of scope, recorded so it is not lost

| Item | Why deferred |
|---|---|
| **Defect 2** — rejected-then-abandoned PRs | Needs non-merged PRs collected as first-class rows with authors, which grows `metrics.json` and changes 接受率's shape. Own spec |
| `approvals` truncation past 50 reviews | Pre-existing, affects `core-without-double-review` only, unrelated to rework |
| Bot reviewers' rejections | `_is_bot` filters them out. Defensible while the metric means "human gate", but worth revisiting as AI review adoption grows |
| `FIX_RE` / `FAIL_RE` are English-prefix-only | [aggregate.js:16-17](../docs/js/aggregate.js). A team writing Chinese PR titles gets 修復佔比 and 變更失敗率 reading 0%, which reads as perfect health rather than "no signal". Documented behaviour ([README.md:89](../README.md)), not a defect — flagged because the 0% is easy to misread |
| `reviewed` / `human_reviews` not time-filtered | The generic `reviews(first:50)` connection ([collect_github.py:104](../scripts/collect_github.py)) does not select `submittedAt`, so `reviewed=sig.human_reviews > 0` ([collect_github.py:716](../scripts/collect_github.py)) cannot be filtered to pre-merge like `rejections` is ([collect_github.py:687](../scripts/collect_github.py)). A PR merged with zero pre-merge human review, whose only review is a post-merge `CHANGES_REQUESTED`, still gets `reviewed=True`, `rework=0`, and escapes `merged-without-review` — it sits in the 打回率 denominator contributing nothing to the numerator. Not a regression: the old denominator was all merged PRs, and `merged-without-review` was already suppressed by any review regardless of timing. Fixing it means adding `submittedAt` to the `reviews` connection and would widen a governance red line — needs the project owner's explicit decision, same as the post-merge-rejection rule did |
| Three API truncation residuals | `reviews(first:50)` — if the first 50 nodes are all bot / `PENDING` / self-authored, `human_reviews` is 0 so `reviewed` is false, while the separate `rejections:` connection still yields a rejection; the PR then vanishes from the KPI (aggregate nests rework under `reviewed`) while its `↩N` badge still renders in the table — deflates, needs 50 non-qualifying reviews so vanishingly rare. `commits(first:50)` — a PR with more than 50 commits loses later `committedDate` values, so rejections that should have been separated by a push merge into one round — under-counts rounds, the opposite direction from the documented force-push over-count (§3.3). `timelineItems(first:20)` — caps recovered dismissed rejections at 20 — under-counts |

## 8. Files touched

| File | Change |
|---|---|
| `scripts/collect_github.py` | Query, `PrSignals`, `rework_rounds()`, `Task`, author-filter ordering |
| `scripts/test_collect_github.py` | Rewrite one assertion, add eight tests |
| `docs/js/aggregate.js` | Four counters |
| `docs/js/render-kpi.js` | 打回率 rewrite, new card, 接受率 scope guard |
| `docs/js/render-table.js` | Badge tooltip |
| `docs/index.html` | Fifth KPI block, card-note |
| `docs/css/dashboard.css` | `.qgrid` 4 → 5 columns |
| `README.md` | Four definition sites |
| `scripts/fixtures/*.json`, `docs/data/demo-data.js` | New fields |
