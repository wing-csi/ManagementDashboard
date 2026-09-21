/**
 * i18n dictionary — namespace: product
 * Language: en (English)
 * Feeds: docs/js/render-product.js and docs/data/demo-outcomes.js.
 *
 * Do not add keys here without a matching key in
 * docs/js/i18n/dict/zh/product.js.
 */
export default Object.freeze({
  readiness: {
    ready: 'Ready',
    onTrack: 'On track',
    watch: 'Watch',
    atRisk: 'At risk',
    unavailable: 'No scope',
  },
  sourceLabel: {
    milestone: 'Milestone',
    plan: 'Plan',
  },

  readinessEmpty: 'No repositories in this scope.',
  roadmapEmpty: 'No milestones or plan sections.',
  noCiData: 'No CI data',
  ciValue: 'CI {value}%',
  noDueDate: 'No due date',
  dueLabel: 'Due {due}',
  noReleaseHistory: 'No release history',
  lastReleaseLabel: 'Last release {date}',
  noScope: 'No milestone / plan scope',
  blockerCount: { one: '{n} blocker', other: '{n} blockers' },
  roadmapShown: 'Showing {shown} / {total}',
  roadmapCount: { one: '{n} large work item', other: '{n} large work items' },

  outcomesTitle: 'Outcomes',
  outcomesEmpty: 'No outcome data in this scope.',
  outcomes: {
    weeklyActiveAccounts: { label: 'Weekly active accounts', unit: { one: '{value} account', other: '{value} accounts' } },
    activationWithin7Days: { label: 'Activation within 7 days', unit: '{value}%' },
    reconciliationTime: { label: 'Reconciliation time', unit: '{value} h' },
    supportRequestsPer1kOrders: { label: 'Support requests / 1,000 orders', unit: { one: '{value} request', other: '{value} requests' } },
    monthlyActiveFilers: { label: 'Monthly active filers', unit: { one: '{value} user', other: '{value} users' } },
    pdfExportUsage: { label: 'PDF export usage', unit: '{value}%' },
    avgTimeSaved: { label: 'Avg. time saved', unit: '{value} min' },
    taxCheckSuccessRate: { label: 'Tax-check success rate', unit: '{value}%' },
  },
});
