/**
 * i18n dictionary — namespace: kpi
 * Language: en (English)
 * Feeds: docs/js/render-kpi.js.
 *
 * Wording follows specs/i18n-terminology.md where a term is listed there.
 * Word order differs from the zh source in several places (e.g. the DORA
 * "avg. 1 every N weeks" fallback) — this is intentional, not a mistranslation.
 */
export default Object.freeze({
  mode: {
    auto: 'Auto',
    manual: 'Manual',
  },
  method: {
    label: 'Label',
    rule: 'Rule',
    trailer: 'Trailer',
    inference: 'Inference',
  },
  events: {
    deployments: 'deployments',
    tags: 'tags',
    releases: 'releases',
  },
  delta: '{arrow} {value}{unit} vs previous period',
  units: {
    pp: ' pp',
    count: '',
    perWeek: '<span class="unit">/week</span>',
    times: '<span class="unit">times</span>',
  },
  fmtHours: {
    hours: '{h} <span class="unit">h</span>',
    days: '{d} <span class="unit">d</span>',
  },
  tasksSub: {
    one: '{count} task · mode: {mode}',
    other: '{count} tasks · mode: {mode}',
  },
  untaggedSub: {
    one: '{count} unclassified task',
    other: '{count} unclassified tasks',
  },
  specNote: 'Classified {tagged} / {total}',
  chartYAxis: 'Tasks',
  alerts: {
    l3DownTitle: 'L3+ share down {n} pp week-over-week',
    l3DownDetail: '{a}% → {b}%. Check whether the work mix shifted, or whether the test framework / toolchain broke.',
    l3UpTitle: 'L3+ share up {n} pp week-over-week',
    l3UpDetail: '{a}% → {b}%.',
    lowCoverageTitle: 'Classification coverage low ({n}%)',
    lowCoverageDetail: 'Add an ai-level label to PRs, or an AI-Level trailer in the commit / PR body — otherwise the metric will be skewed.',
    l3MilestoneTitle: 'L3+ share crossed the 30% milestone',
    l3MilestoneDetail: 'This period {cur}%, previous period {prev}%.',
    noHighAutonomyTitle: 'No L4+ work in the last two weeks',
    noHighAutonomyDetail: 'High-autonomy workflows (end-to-end pipeline + automated verification) may have been disabled.',
    redLine: 'Red line',
    warning: 'Warning',
    violationTitle: {
      one: '{prefix}: {n} task {label}',
      other: '{prefix}: {n} tasks {label}',
    },
    violationRedDetail: 'One of the four hard red-line rules — requires review and follow-up; rows are flagged ⛔ in the table.',
    violationWarnDetail: 'Rows are flagged ⛔ in the table.',
    reworkUpTitle: 'Rework share up {n} pp',
    reworkUpDetail: '{pf}% → {cf}%, possibly a quality issue from the previous period surfacing.',
    suspectTitle: {
      one: "{n} task's claimed level conflicts with its PR behavior",
      other: "{n} tasks' claimed level conflicts with their PR behavior",
    },
    suspectDetail: 'Rows are flagged ⚠ in the table: claimed L4/L5, but manual involvement was observed (review / mixed commits / no tests) — recommend a re-check.',
    collectionFailedTitle: {
      one: '{n} repository failed to collect',
      other: '{n} repositories failed to collect',
    },
    none: 'No anomalies — metrics are within normal range.',
  },
  dora: {
    noRecords: 'No tag / release / deployment records',
    deploySub: {
      one: '{n} event ({label})',
      other: '{n} events ({label})',
    },
    deploySubLow: '{days} days ({label}) · avg. 1 every {weeks} weeks',
    noWorkInScope: 'No work in this range',
    remedySub: {
      one: '{n} / {total} task is remediation',
      other: '{n} / {total} tasks are remediation',
    },
  },
  rag: {
    insufficient: 'Insufficient data',
    red: 'Red',
    amber: 'Amber',
    green: 'Green',
    ciRate: 'CI pass rate {rate}% ({pass}/{total})',
    coverage: 'Test coverage {coverage}%',
    security: 'Security: critical {critical} / high {high} / medium {medium}',
    noData: 'No CI checks / quality data file',
  },
  quality: {
    fixSub: '{fix} fix / revert tasks, out of {total}',
    reworkSub: '{n} / {total} reviewed PRs sent back for rework',
    reworkMedianRounds: ' · median {n} rounds',
    noReviewedPRs: 'No reviewed PRs in this range',
    noPRs: 'No PRs in this range',
    turnSubCounted: {
      one: 'First rework to merge · {n} PR',
      other: 'First rework to merge · {n} PRs',
    },
    turnSubPostMerge: 'All rework PRs received their rework after merge — no turnaround time to compute',
    turnSubNone: 'No reworked PRs in this range',
    acceptNeedsAllScope: 'Requires all-contributors scope (closed PRs have no per-person dimension)',
    acceptSub: '{merged} merged / {closed} closed without merging',
    noDefectFile: 'No repository has a defect data file configured',
    defectFoundBit: '{found} found within {days} days / {denom} tasks',
    defectOpenBit: '{n} open',
    defectUndatedBit: '{n} without a found date',
    defectTruncatedBit: 'List truncated',
    noClassifiedWork: 'No classified work',
  },
  violations: {
    'direct-push-main': 'Direct push to a monitored branch (no PR)',
    'forbidden-files': 'Committed .env / node_modules / __pycache__',
    'workflow-deleted': 'Deleted a GitHub Actions workflow',
    'cross-branch-merge': 'Cross-feature-branch merge',
    'core-without-double-review': 'Core module change without double review',
    'merged-without-review': 'Merged without any review',
    'oversized-pr': 'Oversized PR (not staged into smaller commits)',
  },
});
