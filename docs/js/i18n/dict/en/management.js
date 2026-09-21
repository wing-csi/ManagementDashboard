/**
 * i18n dictionary — namespace: management
 * Language: en (English)
 * Feeds: docs/js/render-management.js and docs/js/management.js.
 *
 * Wording follows specs/i18n-terminology.md exactly where a row exists
 * there. Do not add keys here without a matching key in
 * docs/js/i18n/dict/zh/management.js.
 */
export default Object.freeze({
  status: {
    onTrack: 'On track',
    atRisk: 'At risk',
    offTrack: 'Off track',
    unknown: 'Unknown',
  },
  health: {
    healthy: 'Current',
    attention: 'Needs attention',
    stale: 'Stale',
    unreadable: 'Unknown',
    future: 'Clock mismatch',
    unknown: 'Unknown',
  },
  confidence: {
    actual: 'Actual',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  },
  forecastReason: {
    noPlan: 'No plan',
    notEnoughHistory: 'Too few observations',
    historyTooShort: 'Under 7 days of history',
    noObservedProgress: 'No observed progress',
  },
  headline: {
    countOffTrack: { one: '{n} project off track', other: '{n} projects off track' },
    countAtRisk: { one: '{n} project at risk', other: '{n} projects at risk' },
    countUnknown: { one: '{n} project unknown', other: '{n} projects unknown' },
    countOnTrack: { one: '{n} project on track', other: '{n} projects on track' },
    planningRatio: '{planning}/{repos} planned',
    historyRatio: '{planHistory}/{repos} with history',
    errorsCount: { one: '{n} error', other: '{n} errors' },
  },
  scope: {
    noNetChange: 'No net scope change',
    netChange: 'Net scope change {net}',
    added: 'Added {n}',
    removed: 'Removed {n}',
    historyRatio: '{historyRepos}/{scopeRepos} with history',
    planCount: { one: '{n} plan', other: '{n} plans' },
    noHistory: 'No scope history',
    noPlanHistory: 'No plan history yet',
  },
  forecast: {
    lateCount: { one: '{n} forecast late', other: '{n} forecasts late' },
    reposWithScope: 'repositories with planned scope',
    noScope: 'No planned scope',
    complete: 'Complete',
    unavailable: 'Forecast unavailable',
    projected: 'Forecast {date} · {confidence} confidence',
    lateSuffix: ' · past target date',
  },
  project: {
    scopeChange: 'Scope {net}',
    noKnownRisk: 'No known risk',
    ownerSuffix: ' · Owner {owner}',
    emptyScope: 'No repositories in this scope.',
  },
  attention: {
    empty: 'No known items need immediate follow-up right now.',
    staleDataTitle: 'Dashboard data not fresh',
    generatedAtDetail: 'Generated at {ts}',
    issueCollectionFailedTitle: {
      one: '{n} repository could not collect GitHub Issues',
      other: '{n} repositories could not collect GitHub Issues',
    },
    repoCollectionFailedTitle: 'Repository collection failed',
    dueDetail: '{repo} · Due {due}',
    forecastLateTitle: '{repo} forecast late for target date',
    forecastLateDetail: 'Forecast {projected} · Due {due} · {confidence} confidence',
    redlineLabel: 'Governance redline',
    ciFailLabel: 'CI failed',
    repoLabelDetail: '{repo} · {label}',
  },
  reasons: {
    staleSnapshot: 'Snapshot not fresh',
    issueCollectionFailed: 'GitHub Issue collection failed',
    highOverdue: { one: '{n} high-priority item overdue', other: '{n} high-priority items overdue' },
    duePassed: 'Plan target date has passed',
    overdueCount: { one: '{n} project overdue', other: '{n} projects overdue' },
    staleIssues: { one: '{n} GitHub Issue stalled', other: '{n} GitHub Issues stalled' },
    spi: 'SPI {spi}',
    ciPass: 'CI {pct}%',
    redlines: { one: '{n} governance redline', other: '{n} governance redlines' },
  },
});
