/**
 * i18n dictionary — namespace: misc
 * Language: en (English)
 * Feeds: catch-all for copy not owned by another namespace — panel headings,
 *        card-notes, table headers and filter controls in docs/index.html
 *        (owned by this track: TRACK A / static chrome), plus
 *        docs/js/staleness.js.
 */
export default Object.freeze({
  // <h2> headings
  h2ManagementAttention: 'Management attention needed',
  h2ProjectOutlook: 'Project outlook',
  h2SpectrumDistribution: 'Automation level distribution',
  h2WeeklyMixTrend: 'Weekly task mix × L3+ trend',
  h2Alerts: 'Alerts',
  h2QualityAutomation: 'Quality × automation',
  h2DefectTracking: 'Defect tracking',
  h2ProjectProgress: 'Project progress',
  h2RepoOverview: 'Repository overview',
  h2ReleaseReadiness: 'Release readiness',
  h2RecentTasks: 'Recent tasks',
  // shared between the <h2> and the <div class="label"> that repeat it
  roadmapEpics: 'Roadmap / epics',

  // .card-note
  cardNoteAttentionScope: 'Overdue · data failures · forecast · CI · governance redlines',
  cardNoteProjectOutlook: 'Rule-based status · no data is always shown as "Unknown"',
  cardNoteWeeklyMix: 'Bars = tasks per week · line = L3+ %',
  cardNoteQuality: 'fix / hotfix / revert title prefixes · changes-requested rounds (split by push)',
  cardNoteDefectSourcePrefix: 'Source: GitHub Issues tagged bug + plan file ',
  cardNoteDefectSourceSuffix: ' · unfixed first · ',
  cardNoteProjectProgress: 'Source: GitHub Issues / milestones · completion is computed from created Issues',
  cardNoteRepoOverview: 'Languages measured by bytes · monthly activity is not affected by the time window',
  cardNoteReleaseReadiness: 'Scope completion · blockers · CI · deadline · last release',
  cardNoteTasksTable: 'Each task shows its PR · direct commits are marked No PR',

  // .proj-h
  projHLateWork: 'Exceptions (delayed / stalled >14 days)',
  projHTodayPriority: "Suggested priorities for today",
  projHCodebase: 'Codebase (language mix)',
  projHCommitTypes: 'Commit types (within time window)',
  projHMonthlyActivity: 'Monthly activity (full collection range)',
  projHContributors: 'Contributors',

  // .label
  labelPortfolioDelivery: 'Portfolio delivery',
  labelDataHealth: 'Data health',
  labelCurrentScope: 'Current plan scope',
  labelForecastCoverage: 'Forecast coverage',
  labelL3Hero: 'L3+ share — North Star',
  labelLocApprox: 'AI-written code (approx.)',
  labelClassifiedTasks: 'Classified tasks',
  labelClassificationCoverage: 'Classification coverage',
  labelReleaseCount: 'Releases',
  labelReadyToRelease: 'Ready to release',
  labelOutcomeDataCoverage: 'Outcome data coverage',
  labelDefectRate: 'Defect rate',
  labelReworkShare: 'Rework share',
  labelChangesRequestedRate: 'Changes-requested rate',
  labelReworkTurnaround: 'Rework turnaround time',
  labelPrAcceptRate: 'PR acceptance rate',
  labelEffectiveTasksPerWeek: 'Effective tasks / week',
  labelReworkByLevel: 'Rework share by level',

  // <th>
  thId: 'ID',
  thRepo: 'Repository',
  thSeverity: 'Severity',
  thDescription: 'Description',
  thStatus: 'Status',
  thOwner: 'Owner',
  thDeadline: 'Deadline',
  thDate: 'Date',
  thAuthor: 'Author',
  thPr: 'PR',
  thBranch: 'Branch',
  thTitle: 'Title',
  thLevel: 'Level',
  thDelta: '± lines',

  // level / status filter buttons
  filterAll: 'All',
  levelNone: 'Unclassified',
  statusRedline: 'Redline',
  statusWarning: 'Governance warning',
  statusSuspect: 'Level mismatch',
  statusCiFail: 'CI failed',
  levelFilterLabel: 'Level',
  statusFilterLabel: 'Status',

  // task search
  taskSearchPlaceholder: 'Search title / author / branch / PR',
  taskSearchAriaLabel: 'Search tasks',

  // docs/js/staleness.js — {days} is the interpolated age in days
  staleMessage: 'This data is a {days}-day-old snapshot; all "today", overdue, and forecast figures are based on stale data. Check GitHub Actions for the latest collection and deployment workflow runs.',
  unreadableMessage: "Could not read the data's timestamp, so it's unclear when this page's numbers are from. Check the generated_at field in metrics.json.",
  futureMessage: "The data's timestamp is in the future — the local clock or the data collector's clock is wrong. All \"today\", overdue, and SPI figures on this page cannot be trusted.",

  // Follow-up sweep: remaining static text in docs/index.html
  managementSummaryAriaLabel: 'Management summary',
  subL3Hero: 'Share of work led primarily by AI agents',
  subLocApprox: 'Share of inserted lines from L2+ work',
  thresholdL3: 'L3 automation threshold',
  ragHintPrefix: 'Gray light = no quality signal (PR needs a CI check, or specify ',
  ragHintSuffix: ' in the config file) — see the README for quality metrics',
  scopeNoteRagFullRepo: 'Red/yellow/green status is repo-wide',
  subEffectiveTasks: 'Work with ≥10 changed lines',
  scopeNoteFullRepo: 'Repo-wide',
  h3PlanAssignment: 'Plan task assignment',
  pPlanAssignmentDesc: 'assignee:Name / @GitHub-handle tasks ÷ total plan tasks · unmarked tasks use the repository owner',
  h3DefectFix: 'Defect fix distribution',
  pDefectFixDesc: 'fixed-by:Name · unfixed defects are still counted',
  subRoadmapEpics: 'Milestones + plan segments',
  subReleaseCount: 'Current time window · uses deployments, then tags, then release records',
  subReadyToRelease: 'Ready / repositories with a planned scope',
  subOutcomeDataCoverage: 'Has an outcome data file / repositories in scope',
  loadMore: 'Load more',
});
