/**
 * i18n dictionary — namespace: chrome
 * Language: en (English)
 * Feeds: docs/index.html (masthead, tabs, filters, load-error banner,
 *        footer) and the dynamic chrome built in docs/js/main.js (eyebrow,
 *        repo/branch/contributor select options, footStamp).
 *
 * Tab labels are deliberately ONE WORD each — see specs/i18n-terminology.md
 * "Hard constraint: tab labels stay short". Do not "improve" them.
 */
export default Object.freeze({
  title: 'AI Autonomy Gauge',
  brand: 'Autonomy Gauge',
  telemetry: 'GITHUB TELEMETRY',
  demoBadge: 'Demo data · explicitly requested (?demo=1)',

  repoAriaLabel: 'Repository',
  branchAriaLabel: 'Branch',
  contributorAriaLabel: 'Contributor',
  windowAriaLabel: 'Time window',

  window30: 'Last 30 days',
  window60: 'Last 60 days',
  window90: 'Last 90 days',
  window180: 'Last 180 days',

  tablistAriaLabel: 'Dashboard tabs',
  tabOverview: 'Overview',
  tabQuality: 'Quality',
  tabProjects: 'Projects',
  tabProduct: 'Product',
  tabTasks: 'Tasks',

  loadErrorTitle: 'Failed to load data.',
  loadErrorSignedOut: 'Not signed in, or the session has expired?',
  loadErrorRelogin: 'sign in again',
  loadErrorDemoHint: '. Want to see demo data: ',

  footerSource: 'Data source: GitHub GraphQL API → scripts/collect_github.py → GitHub Actions (nightly verification) → local view',

  // Built dynamically in docs/js/main.js
  repoCount: { one: '{n} repository', other: '{n} repositories' },
  ownerLabel: 'Owner {name}',
  byOwnerGroup: 'By owner',
  individualReposGroup: 'Individual repositories',
  ownerProjectsOption: "{owner}'s projects ({n})",
  allRepos: 'All repositories',
  allBranches: 'All branches',
  allContributors: 'All contributors',
  branchSelectTitle: 'Select a single repository to filter by branch',
  signInRequired: 'Sign-in required.',
  networkError: 'network error',
  loadErrorDetailWrapped: '({detail})',
  generatedAt: 'Generated {ts}',

  // DORA strip — kept in chrome (not kpi) because docs/index.html is
  // exclusively this track's file; see specs/i18n-terminology.md Core metrics.
  doraDeployFreq: 'Deployment frequency',
  doraLeadTime: 'Lead time (to merge)',
  doraLeadTimeSub: 'Median time from PR open to merge',
  doraChangeFailureRate: 'Change failure rate',
  doraChangeFailureRateSub: 'Remedial work ÷ all work',
  doraMttr: 'MTTR (approx.)',
  doraMttrSub: 'Median lead time for fix-type work',
});
