/**
 * i18n dictionary — namespace: burndown
 * Language: en (English)
 * Feeds: docs/js/render-burndown.js and docs/js/burndown.js.
 *
 * Wording follows specs/i18n-terminology.md where a term appears there.
 * Terms not in that table (this file's own reason/status vocabulary) are
 * decided locally, consistently with its tone.
 */
export default Object.freeze({
  na: '—',
  caption: {
    singlePoint: 'Only one observation so far — not yet a trend',
    truncated: 'History has been truncated — the ideal line starts from the earliest remaining observation',
    backfilled: 'Completion trend backfilled from {tasks} task done: dates (covers {pct}%); scope change counts only real plan snapshots',
  },
  idealCaption: {
    noDue: 'plan.md has no due: — no ideal line',
    dueUnusable: "plan.md's due: is not a valid date — no ideal line",
    dueNotAfterStart: 'due: is not after the start, so no ideal line can be drawn',
    default: 'No ideal line',
  },
  startCaption: {
    plan: 'Start: plan.md start:',
    repo: "Start: repo's first commit",
    observation: 'Start: first plan.md change',
  },
  startReasonCaption: {
    startUnusable: "plan.md's start: is not a plottable date",
    startAfterHistory: 'start: is later than the first observation — not used',
  },
  forecastReason: {
    noPlan: 'No plan scope',
    notEnoughHistory: 'Needs at least 2 observations',
    historyTooShort: 'Needs at least 7 days of history',
    noObservedProgress: 'No observed completion rate',
  },
  statusLabel: {
    complete: 'Complete',
    onTrack: 'On track',
    atRisk: 'At risk',
    offTrack: 'Off track',
    unknown: 'Trend unclear',
  },
  target: {
    label: 'Target date',
    dateInvalid: 'plan.md date invalid',
    dueNotAfterStart: 'Target date is not after the start',
    notSet: 'Not set in plan.md',
    cannotCompute: 'Cannot compute days remaining',
    daysLeft: '{n} d left',
    overdueDays: '{n} d overdue',
  },
  scope: {
    label: 'Scope change',
    noBaseline: 'No historical baseline',
    sinceDate: 'since {date}',
    fromStart: 'from the start',
    detail: '{prefix} {baseline} → now {current}',
  },
  forecast: {
    label: 'Forecast completion',
    completeValue: 'Complete',
    actualResult: 'Actual result',
    unavailable: 'Not available yet',
    rateDetail: '{rate} / week · {confidence} confidence',
    confidenceHigh: 'High',
    confidenceMedium: 'Medium',
    confidenceLow: 'Low',
    late: ' · {n} d late',
    early: ' · {n} d early',
    onTime: ' · on time',
  },
  headline: {
    allComplete: 'The full plan scope is complete',
    behind: "Actual progress is {n} pp behind today's plan",
    ahead: "Actual progress is {n} pp ahead of today's plan",
    onIdeal: 'Actual progress matches the ideal line',
    insufficientData: 'Not enough data yet to judge the progress gap',
    aboveIdeal: {
      one: '{n} more task outstanding than the ideal line',
      other: '{n} more tasks outstanding than the ideal line',
    },
    overdueCount: { one: '{n} task overdue', other: '{n} tasks overdue' },
  },
  summary: {
    progressLabel: 'Completion',
    progressDetail: '{done} / {total} complete',
    remainingLabel: 'Remaining work',
    remainingDetail: 'tasks outstanding',
  },
  source: {
    backfilledKind: 'task done: dates + commit history',
    commitKind: 'commit history',
    asOf: 'Data as of {date} · updated daily at 05:00 HKT',
    prefix: 'Source: {link} {kind}',
  },
  chart: {
    ariaLabel: '{repo} remaining-work burndown chart',
    headTitle: 'Remaining work trend',
    headHint: 'Lower is better',
    emptyTitle: 'Not enough observations to draw a trend',
    emptyHint: 'Only 1 plan.md history point so far; the progress and deadlines above are still usable.',
    datasetRemaining: 'Remaining',
    datasetScope: 'Scope cap',
    datasetIdeal: 'Ideal remaining',
    yAxisTitle: 'Task count',
    tooltipLabel: '{label}: {value}',
    todayLabel: 'Today',
  },
  details: {
    summary: {
      one: 'View the deadline for {n} unfinished task',
      other: 'View deadlines for {n} unfinished tasks',
    },
  },
});
