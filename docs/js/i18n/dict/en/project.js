/**
 * i18n dictionary — namespace: project
 * Language: en (English)
 * Feeds: docs/js/render-project.js.
 *
 * Wording follows specs/i18n-terminology.md exactly where a row exists
 * there. Do not add keys here without a matching key in
 * docs/js/i18n/dict/zh/project.js.
 */
export default Object.freeze({
  priority: {
    p0: 'P0 / Critical',
    high: 'High priority',
    medium: 'Medium priority',
  },
  labels: {
    bug: 'Defect',
  },
  overdueDays: { one: '{n} day overdue', other: '{n} days overdue' },
  openDays: { one: 'open {n} day', other: 'open {n} days' },
  chip: {
    owner: '· Owner {owner}',
    unspecifiedOwner: 'Unspecified',
    tooltipSourceLabel: 'Scope source: {path} ({done}/{total} checkboxes)',
    tooltipWithIssues: ' · Anomalies / suggestions from GitHub Issues',
    tooltipWithoutIssues: ' · No GitHub Issues used — no date / priority data',
    completionPlan: 'Completion {pct}%({done}/{total} · plan.md)',
    noIssuesOrPlan: 'No GitHub Issues / plan file used',
    issueTooltip: 'Completed {done} / Remaining {open} · Overdue {overdue} · Stalled {stale} · Denominator = created GitHub Issues; scope not yet split into Issues cannot be shown',
    completionIssues: 'Completion {pct}%({done}/{total})· {risk}',
  },
  risk: {
    high: 'High risk',
    medium: 'Medium risk',
    normal: 'Normal',
  },
  milestone: {
    due: ' · Due {due}',
    planLabel: 'Plan',
    sectionTooltip: '{title} ({path})',
  },
  late: {
    staleDays: { one: '{n} day since update', other: '{n} days since update' },
  },
  empty: {
    noPlanningData: 'No planning data in this scope — use GitHub Issues (each Issue represents one item of work, with due dates set on milestones), or point the config at a plan file (Markdown checkboxes).',
    noLateWork: 'No overdue or stalled work right now.',
    noTodoWork: 'No pending GitHub Issues — the to-do list is clear.',
  },
});
