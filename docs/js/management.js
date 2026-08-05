import { DAY, realDate, toISO, toMs } from './plan-dates.js';
import { timelineStrip } from './timeline.js';
import { staleness } from './staleness.js';

const HIGH_RE = /^(p0|p1|critical|high|blocker|urgent|priority:\s*(urgent|highest|high))$/i;
const REDLINES = new Set([
  'direct-push-main', 'forbidden-files', 'workflow-deleted',
  'cross-branch-merge', 'core-without-double-review',
]);
const STATUS_RANK = { 'on-track': 0, unknown: 1, 'at-risk': 2, 'off-track': 3 };

const dateDiff = (from, to) => Math.round((toMs(to) - toMs(from)) / DAY);
const addDays = (date, days) => toISO(toMs(date) + days * DAY);
const planUrl = (repo, plan) =>
  `https://github.com/${repo}/blob/${plan.ref || 'HEAD'}/${plan.path}`;

function observations(plan, todayStr) {
  const rows = (Array.isArray(plan?.history) ? plan.history : [])
    .filter((p) => p && realDate(p.date) && Number.isFinite(p.done) && Number.isFinite(p.total))
    .map((p) => ({ date: p.date, done: p.done, total: p.total }))
    .sort((a, b) => a.date.localeCompare(b.date));
  if (!rows.length) return rows;
  if (realDate(todayStr) && Number.isFinite(plan?.done) && Number.isFinite(plan?.total)) {
    const current = { date: todayStr, done: plan.done, total: plan.total };
    const last = rows.at(-1);
    if (!last || last.date !== current.date || last.done !== current.done || last.total !== current.total) {
      rows.push(current);
      rows.sort((a, b) => a.date.localeCompare(b.date));
    }
  }
  // Multiple plan commits on one day are possible; the last observation wins.
  return [...new Map(rows.map((p) => [p.date, p])).values()];
}

export function scopeChange(plan, todayStr) {
  const rows = observations(plan, todayStr);
  if (!rows.length) {
    return { available: false, reason: 'no-history', baseline: null, current: plan?.total ?? null,
             net: null, added: null, removed: null, observations: 0 };
  }
  let added = 0, removed = 0;
  for (let i = 1; i < rows.length; i++) {
    const delta = rows[i].total - rows[i - 1].total;
    if (delta > 0) added += delta;
    if (delta < 0) removed += Math.abs(delta);
  }
  const baseline = rows[0].total;
  const current = rows.at(-1).total;
  return { available: true, reason: rows.length < 2 ? 'baseline-only' : null,
           baseline, current, net: current - baseline, added, removed,
           observations: rows.length };
}

/** A deliberately guarded projection, not a commitment date.
 *
 * We require at least seven days of history and positive observed completion.
 * Scope movement lowers confidence because completed-count deltas are no longer
 * a clean measure of burn. Missing evidence returns an explicit reason.
 */
export function completionForecast(plan, todayStr) {
  if (!plan || !(plan.total > 0)) return { status: 'unavailable', reason: 'no-plan' };
  const remaining = Math.max(0, plan.total - (plan.done || 0));
  if (remaining === 0) {
    return { status: 'complete', reason: null, projected: todayStr, remaining: 0,
             confidence: 'actual', ratePerWeek: null, late: false };
  }
  const rows = observations(plan, todayStr);
  if (rows.length < 2) return { status: 'unavailable', reason: 'not-enough-history', remaining };
  const span = dateDiff(rows[0].date, rows.at(-1).date);
  if (span < 7) return { status: 'unavailable', reason: 'history-too-short', remaining };
  let completed = 0;
  for (let i = 1; i < rows.length; i++) completed += Math.max(0, rows[i].done - rows[i - 1].done);
  if (!(completed > 0)) return { status: 'unavailable', reason: 'no-observed-progress', remaining };
  const ratePerDay = completed / span;
  const projected = addDays(rows.at(-1).date, Math.ceil(remaining / ratePerDay));
  const change = scopeChange(plan, todayStr);
  const moved = (change.added || 0) + (change.removed || 0) > 0;
  const confidence = rows.length >= 8 && span >= 28 && !moved ? 'high'
    : rows.length >= 4 && span >= 14 && !moved ? 'medium' : 'low';
  const due = realDate(plan.due_max) ? plan.due_max : null;
  return { status: 'forecast', reason: null, projected, remaining, confidence,
           ratePerWeek: +(ratePerDay * 7).toFixed(1), due, late: !!due && projected > due };
}

export function dataHealth(data, repos, nowMs) {
  const freshness = staleness(data?.generated_at, nowMs);
  const rm = data?.repo_meta || {};
  const counts = { repos: repos.length, planning: 0, planHistory: 0, quality: 0,
                   defects: 0, issueErrors: 0, repoErrors: 0 };
  const issueErrors = [];
  for (const repo of repos) {
    const meta = rm[repo] || {};
    if (meta.plan || meta.issues) counts.planning++;
    if (Array.isArray(meta.plan?.history) && meta.plan.history.length) counts.planHistory++;
    if (meta.quality) counts.quality++;
    if (meta.defects) counts.defects++;
    if (meta.issues_error) {
      counts.issueErrors++;
      issueErrors.push({ repo, message: String(meta.issues_error) });
    }
  }
  const errors = (data?.errors || []).map(String);
  counts.repoErrors = errors.length;
  let status = 'healthy';
  if (freshness.status !== 'fresh') status = freshness.status;
  else if (errors.length || issueErrors.length) status = 'attention';
  else if (!repos.length || counts.planning === 0) status = 'unknown';
  return { status, freshness, counts, issueErrors, errors };
}

function planningScope(meta) {
  if (meta.plan && meta.plan.total > 0) {
    return { source: 'plan', title: meta.plan.path || 'plan', done: meta.plan.done || 0,
             total: meta.plan.total, due: realDate(meta.plan.due_max) ? meta.plan.due_max : null };
  }
  const milestones = (meta.issues?.milestones || [])
    .filter((m) => (m.open || 0) + (m.closed || 0) > 0)
    .sort((a, b) => (a.due || '9999-12-31').localeCompare(b.due || '9999-12-31'));
  const milestone = milestones.find((m) => (m.open || 0) > 0) || milestones.at(-1);
  return milestone ? { source: 'milestone', title: milestone.title, done: milestone.closed || 0,
    total: (milestone.open || 0) + (milestone.closed || 0),
    due: realDate(milestone.due) ? milestone.due : null } : null;
}

export function projectOutlook(data, repo, tasks, todayStr, freshnessStatus = 'fresh') {
  const meta = (data.repo_meta || {})[repo] || {};
  const scope = planningScope(meta);
  const plan = meta.plan || null;
  const issueOpen = meta.issues?.open || [];
  const planOpen = plan?.open_tasks || [];
  const overdueIssues = issueOpen.filter((i) => realDate(i.due) && i.due < todayStr);
  const overduePlan = planOpen.filter((i) => realDate(i.due) && i.due < todayStr);
  const highOverdue = overdueIssues.filter((i) => (i.labels || []).some((l) => HIGH_RE.test(l))).length
    + overduePlan.filter((i) => HIGH_RE.test(i.priority || '')).length;
  const staleIssues = issueOpen.filter((i) => realDate(i.updated) && dateDiff(i.updated, todayStr) > 14).length;
  const repoTasks = tasks.filter((t) => t.repo === repo);
  const ci = repoTasks.filter((t) => t.kind === 'pr' && t.ci);
  const ciPass = ci.length ? ci.filter((t) => t.ci === 'pass').length / ci.length * 100 : null;
  const redlines = repoTasks.filter((t) => (t.violations || []).some((v) => REDLINES.has(v))).length;
  const timeline = plan ? timelineStrip(plan, todayStr) : null;
  const spi = timeline?.spi ?? null;
  const duePassed = !!scope?.due && scope.due < todayStr && scope.done < scope.total;
  const inputReasons = [];
  if (freshnessStatus !== 'fresh') inputReasons.push('快照唔新鮮');
  if (meta.issues_error && !plan) inputReasons.push('Issues 收集失敗');
  if (!scope) inputReasons.push('未有 planning scope');
  let status = inputReasons.length ? 'unknown' : 'on-track';
  const reasons = [];
  if (inputReasons.length) {
    reasons.push(...inputReasons);
  } else if (highOverdue || duePassed) {
    status = 'off-track';
    if (highOverdue) reasons.push(`${highOverdue} 個高優先項目逾期`);
    if (duePassed) reasons.push('計劃目標日已過');
  } else {
    const overdue = overdueIssues.length + overduePlan.length;
    if (overdue) reasons.push(`${overdue} 個項目逾期`);
    if (staleIssues) reasons.push(`${staleIssues} 個 issue 呆滯`);
    if (spi != null && spi < 0.8) reasons.push(`SPI ${spi}`);
    if (ciPass != null && ciPass < 90) reasons.push(`CI ${ciPass.toFixed(0)}%`);
    if (redlines) reasons.push(`${redlines} 個治理紅線`);
    if (reasons.length) status = 'at-risk';
  }
  const progress = scope ? scope.done / scope.total * 100 : null;
  return { repo, owner: meta.owner || null, status, reasons, scope, progress, spi,
           overdue: overdueIssues.length + overduePlan.length, highOverdue, staleIssues,
           ciPass, redlines, scopeChange: plan ? scopeChange(plan, todayStr) : null,
           forecast: plan ? completionForecast(plan, todayStr) : { status: 'unavailable', reason: 'no-plan' },
           url: plan ? planUrl(repo, plan) : null };
}

function attentionItems(data, projects, tasks, todayStr, health) {
  const items = [];
  if (health.freshness.status !== 'fresh') {
    items.push({ severity: 'critical', kind: 'data', title: 'Dashboard 數據唔新鮮',
      detail: `generated ${data.generated_at || '—'}`, url: null });
  }
  if (health.issueErrors.length) {
    items.push({ severity: 'critical', kind: 'data',
      title: `${health.issueErrors.length} 個 repo 收集唔到 Issues`,
      detail: health.issueErrors[0].message, url: null });
  }
  for (const message of health.errors.slice(0, 2)) {
    items.push({ severity: 'critical', kind: 'data', title: 'Repo 收集失敗', detail: message, url: null });
  }
  const rm = data.repo_meta || {};
  for (const project of projects) {
    const meta = rm[project.repo] || {};
    for (const issue of meta.issues?.open || []) {
      if (!realDate(issue.due) || issue.due >= todayStr) continue;
      const high = (issue.labels || []).some((l) => HIGH_RE.test(l));
      items.push({ severity: high ? 'critical' : 'warning', kind: 'overdue',
        title: issue.title, detail: `${project.repo.split('/').pop()} · due ${issue.due}`,
        url: issue.url || null });
    }
    for (const item of meta.plan?.open_tasks || []) {
      if (!realDate(item.due) || item.due >= todayStr) continue;
      items.push({ severity: HIGH_RE.test(item.priority || '') ? 'critical' : 'warning',
        kind: 'overdue', title: item.title,
        detail: `${project.repo.split('/').pop()} · due ${item.due}`,
        url: project.url });
    }
    if (project.forecast.status === 'forecast' && project.forecast.late) {
      items.push({ severity: 'warning', kind: 'forecast',
        title: `${project.repo.split('/').pop()} 預測遲過目標日`,
        detail: `預測 ${project.forecast.projected} · due ${project.forecast.due} · ${project.forecast.confidence} confidence`,
        url: project.url });
    }
  }
  for (const task of tasks) {
    const red = (task.violations || []).some((v) => REDLINES.has(v));
    if (red || task.ci === 'fail') {
      items.push({ severity: red ? 'critical' : 'warning', kind: red ? 'redline' : 'ci',
        title: task.title, detail: `${task.repo.split('/').pop()} · ${red ? '治理紅線' : 'CI 失敗'}`,
        url: task.url || null });
    }
  }
  const order = { critical: 0, warning: 1, info: 2 };
  return items.sort((a, b) => order[a.severity] - order[b.severity]).slice(0, 10);
}

export function deriveManagement(data, { repos = data.repos || [], tasks = data.tasks || [],
                                         todayStr = (data.generated_at || '').slice(0, 10),
                                         nowMs = Date.now() } = {}) {
  const health = dataHealth(data, repos, nowMs);
  const projects = repos.map((repo) => projectOutlook(data, repo, tasks, todayStr, health.freshness.status));
  let portfolioStatus = projects.length ? 'on-track' : 'unknown';
  for (const project of projects) {
    if (STATUS_RANK[project.status] > STATUS_RANK[portfolioStatus]) portfolioStatus = project.status;
  }
  if (health.freshness.status !== 'fresh' && STATUS_RANK[portfolioStatus] < STATUS_RANK.unknown) {
    portfolioStatus = 'unknown';
  }
  const changes = projects.map((p) => p.scopeChange).filter((c) => c?.available);
  const planProjects = projects.filter((p) => p.scope?.source === 'plan');
  const forecasts = projects.map((p) => p.forecast).filter((f) => f.status === 'forecast');
  const totals = {
    planning: projects.filter((p) => p.scope).length,
    currentScope: planProjects.reduce((n, p) => n + p.scope.total, 0),
    baselineScope: changes.reduce((n, c) => n + c.baseline, 0),
    net: changes.reduce((n, c) => n + c.net, 0),
    added: changes.reduce((n, c) => n + c.added, 0),
    removed: changes.reduce((n, c) => n + c.removed, 0),
    scopeRepos: planProjects.length,
    historyRepos: changes.length,
    forecastable: forecasts.length,
    forecastLate: forecasts.filter((f) => f.late).length,
  };
  return { health, projects, portfolioStatus, totals,
           attention: attentionItems(data, projects, tasks, todayStr, health) };
}
