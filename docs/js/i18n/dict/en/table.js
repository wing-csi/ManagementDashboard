/**
 * i18n dictionary — namespace: table
 * Language: en (English)
 * Feeds: docs/js/render-table.js.
 *
 * Do not add keys here without a matching key in
 * docs/js/i18n/dict/zh/table.js.
 */
export default Object.freeze({
  typeLabel: {
    feat: 'Feature', fix: 'Fix', hotfix: 'Hotfix', revert: 'Revert', refactor: 'Refactor',
    test: 'Test', docs: 'Docs', chore: 'Chore', build: 'Build', ci: 'CI', perf: 'Perf',
    style: 'Style', other: 'Other',
  },
  unassigned: 'Unassigned',
  fixedUnassigned: 'Fixed · Unassigned',

  pie: {
    planLabel: 'Planned work',
    planSub: 'tasks',
    planEmpty: 'No assignment data available — set a repository owner or task owner.',
    defectLabel: 'Defects',
    defectSub: '{n} fixed',
    defectEmpty: 'No defect data available — use a GitHub Issue tagged bug, a plan-file #bug marker, or the defect register.',
    unfixed: 'Unfixed',
  },

  overview: {
    noLanguageData: 'No language data',
    repoSize: 'Repository size {mb} MB (Git)',
    noWorkInScope: 'No work in this scope',
    noData: 'No data',
    taskCountSuffix: ' tasks',
    scopeShare: '{pct}% of this scope',
  },

  defects: {
    severityHigh: 'High',
    severityMedium: 'Medium',
    severityLow: 'Low',
    countCapped: '{n} items, showing first {cap}',
    count: '{n} items',
    planSource: 'Plan',
    statusOpen: 'Unfixed',
    statusFixed: 'Fixed',
    emptyPrefix: 'No defects — create a GitHub Issue tagged bug, or add a line to the plan file: ',
    emptyCode: '- [ ] … #bug !P1 due:2026-08-01',
  },

  row: {
    directCommitTooltip: 'Direct commit · no owning PR',
    noPr: 'No PR',
    commitTooltip: 'Commit {id}',
    prAriaLabel: 'PR #{id}',
    emptyTable: 'No work in this scope',
    shownCount: 'Showing {shown} / {total} tasks',
  },
});
