# PM-oriented project burndown redesign

Date: 2026-08-05

## Problem

The original card was chart-first. A PM had to infer five separate facts from a wide daily axis, three similar lines and a second timeline: current progress, schedule gap, deadline pressure, scope growth and likely completion date. On long plans the empty runway and dense date labels dominated the actual observations. A one-point series looked precise even though the caption said it was not a trend.

## Decision hierarchy

Every project card must answer these questions in order:

1. Does this project need attention now?
2. How much is done and how much remains?
3. What is the target date and how much time is left?
4. Has scope moved since the first observation?
5. Is there enough evidence for a forecast, and does it land before the target?
6. What history explains that answer?
7. Which unfinished tasks have deadlines?

Questions 1–5 are always visible. The chart answers 6. The task deadline strip answers 7 and is collapsed by default.

## Card contract

### Status callout

- `complete`: no remaining work.
- `off-track`: target has passed, or SPI is below 0.8.
- `at-risk`: unfinished work is overdue, SPI is below 1, or the guarded forecast is late.
- `on-track`: a usable SPI is at least 1 and no stronger risk applies.
- `unknown`: the plan window is not usable yet. Unknown is never rendered as green.

The callout translates SPI into plain language. It reports actual completion minus expected completion in percentage points and, when available, remaining work above the ideal line.

### Five metrics

| Metric | Formula / source | Guard |
|---|---|---|
| Completion | `done / total` | `total = 0` becomes unavailable |
| Remaining | `max(0, total - done)` | never negative |
| Target | resolved plan `due` and calendar days from `generated_at` | invalid or missing dates are named, not substituted |
| Scope movement | current total minus first observed total | no history means no invented baseline |
| Completion forecast | existing guarded observed-velocity forecast | requires at least two observations, seven days and positive completion |

Forecast is a trend projection, not a commitment. The card always includes confidence and observed weekly velocity. When a target exists it shows the forecast delta in days.

### Chart

- Actual remaining: strongest solid line; the current point is visible.
- Scope ceiling: lighter dotted line, retained so scope growth cannot masquerade as lost progress.
- Ideal remaining: neutral dashed line from starting scope to zero on the target date.
- Today: labelled vertical marker.
- X-axis: at most eight horizontal labels; tooltips keep the full date.
- The chart remains blank before the first real observation. No synthetic flat history is added.
- A single historical observation shows an explicit insufficient-data state instead of a horizontal line that could be mistaken for a trend.

All previous invalid-date, missing-history, truncation and start-source caveats remain in force.

## Upstream ownership and cadence

Project identity is one configured repository plus its `plan_file`. Multi-repository projects are out of scope until the upstream contract has an explicit `project_id`; the frontend must not infer grouping from repository names.

```text
plan.md current blob ─────────────┐
plan.md commits + dated blobs ────┼─ collect_github.py ─ metrics.json ─ dashboard
repo first commit ────────────────┘
```

- Owner: `.github/workflows/collect.yml`.
- Scheduled trigger: `0 21 * * *` (daily 05:00 HKT).
- Extra triggers: relevant pushes and manual dispatch.
- Current plan data: GitHub Contents API through `fetch_plan_file`.
- History: GitHub commits filtered by the plan path; the last plan state per calendar day is parsed into `{date, done, total}`.
- Start fallback: declared heading `start:` → repository first commit → first plan observation.
- Transport: successful collection writes `/tmp/metrics.json`; the snapshot is published independently to the private data repo and Cloudflare Pages.
- Freshness: `generated_at`, not the nominal cron time. Existing 48-hour stale handling remains authoritative.
- Failure: collector failure blocks deploy; plan-history failure emits `history_error`; old snapshots with neither history key keep the section hidden for compatibility.

The browser is a snapshot consumer. It does not call GitHub or hold repository credentials.

## Acceptance checks

- The fixture project reads as 25% complete, 9 remaining, target 08/06, scope +2 and no forecast because history is under seven days.
- Its callout says it is behind plan and quantifies the percentage-point gap.
- A sufficiently long positive history shows projected date, confidence and target delta.
- Source, snapshot date and expected cadence are visible without opening documentation.
- Task deadline detail is available but collapsed on first render.
- Existing burndown, timeline, stale-data, typography and responsive-overflow tests continue to pass.
