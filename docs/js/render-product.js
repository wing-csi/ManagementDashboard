import { state, $, esc, refDate, repoInScope, toDate, windowTasks } from './data.js';

const BLOCKER_RE = /^(p0|critical|blocker|urgent|priority:\s*(urgent|highest))$/i;
const READINESS = {
  ready: { label: 'Ready', color: 'var(--good)' },
  'on-track': { label: 'On track', color: '#5F8CC6' },
  watch: { label: 'Watch', color: 'var(--warn)' },
  'at-risk': { label: 'At risk', color: 'var(--alert)' },
  unavailable: { label: '未有 scope', color: '#9AA5A0' },
};

const scopedRepos = () => (state.data.repos || []).filter(repoInScope);
const number = (value) => typeof value === 'number'
  ? value.toLocaleString(undefined, { maximumFractionDigits: 1 })
  : String(value);

function releaseEvents(meta) {
  if ((meta.deployments || []).length) return meta.deployments;
  if ((meta.tags || []).length) return meta.tags;
  return meta.releases || [];
}

function releaseEventsInWindow(meta, from, end) {
  const inWindow = (rows) => (rows || []).filter((d) => {
    const ms = toDate(d).getTime();
    return ms >= from && ms < end;
  });
  const deployments = inWindow(meta.deployments);
  const tags = inWindow(meta.tags);
  const releases = inWindow(meta.releases);
  return deployments.length ? deployments : tags.length ? tags : releases;
}

function milestoneFor(meta) {
  const rows = ((meta.issues || {}).milestones || [])
    .filter((m) => (m.open || 0) + (m.closed || 0) > 0)
    .sort((a, b) => (a.due || '9999-12-31').localeCompare(b.due || '9999-12-31'));
  return rows.find((m) => (m.open || 0) > 0) || rows.at(-1) || null;
}

/** Release readiness is deliberately evidence-based: backlog completion,
 * explicit blockers, due date and CI. Product adoption is never used as a
 * proxy for readiness, and absent planning data stays absent. */
export function readinessForRepo(repo, tasks, todayStr) {
  const meta = (state.data.repo_meta || {})[repo] || {};
  const milestone = milestoneFor(meta);
  const plan = meta.plan;
  const scope = milestone
    ? { title: milestone.title, done: milestone.closed || 0,
        total: (milestone.open || 0) + (milestone.closed || 0), due: milestone.due, source: 'milestone' }
    : plan && plan.total
      ? { title: plan.path || 'plan', done: plan.done || 0, total: plan.total,
          due: plan.due_max || null, source: 'plan' }
      : null;
  const open = ((meta.issues || {}).open || []).filter((i) =>
    !milestone || !i.milestone || i.milestone === milestone.title);
  const planOpen = !milestone && plan ? (plan.open_tasks || []) : [];
  const blockers = open.filter((i) => (i.labels || []).some((l) => BLOCKER_RE.test(l))).length
    + planOpen.filter((i) => i.priority === 'P0').length;
  const ciTasks = tasks.filter((t) => t.repo === repo && t.kind === 'pr' && t.ci);
  const ciPass = ciTasks.length
    ? (ciTasks.filter((t) => t.ci === 'pass').length / ciTasks.length) * 100 : null;
  const progress = scope && scope.total ? (scope.done / scope.total) * 100 : null;
  const days = scope?.due
    ? Math.round((toDate(scope.due) - toDate(todayStr)) / 864e5) : null;
  let status = 'unavailable';
  if (scope) {
    if (blockers || (days != null && days < 0) || (ciPass != null && ciPass < 75)) status = 'at-risk';
    else if (progress >= 90 && (ciPass == null || ciPass >= 90)) status = 'ready';
    else if ((days != null && days <= 14 && progress < 75) || (ciPass != null && ciPass < 90)) status = 'watch';
    else status = 'on-track';
  }
  const events = releaseEvents(meta).slice().sort();
  return { repo, scope, blockers, ciPass, progress, days, status, lastRelease: events.at(-1) || null };
}

function roadmapItems(repos) {
  const rm = state.data.repo_meta || {};
  const out = [];
  for (const repo of repos) {
    const meta = rm[repo] || {};
    for (const ms of (meta.issues || {}).milestones || []) {
      const total = (ms.open || 0) + (ms.closed || 0);
      if (total) out.push({ repo, title: ms.title, done: ms.closed || 0, total, due: ms.due, source: 'milestone' });
    }
    for (const section of (meta.plan || {}).sections || []) {
      if (section.total) out.push({ repo, title: section.title, done: section.done || 0,
        total: section.total, due: null, source: 'plan' });
    }
  }
  return out.sort((a, b) => (a.due || '9999-12-31').localeCompare(b.due || '9999-12-31'));
}

function renderReadiness(rows) {
  $('releaseReadiness').innerHTML = rows.map((row) => {
    const meta = READINESS[row.status];
    const progress = row.progress == null ? '–' : `${row.progress.toFixed(0)}%`;
    const ci = row.ciPass == null ? 'CI 無數據' : `CI ${row.ciPass.toFixed(0)}%`;
    const due = row.scope?.due ? `due ${row.scope.due}` : '未設 due date';
    const last = row.lastRelease ? `上次發佈 ${row.lastRelease}` : '未有發佈記錄';
    return `<article class="release-row">
      <div class="release-title"><span class="readiness-dot" style="background:${meta.color}"></span>
        <strong>${esc(row.repo.split('/').pop())}</strong><span class="readiness-state">${meta.label}</span></div>
      <div class="release-scope">${row.scope ? `${esc(row.scope.title)} · ${progress}` : '未有 milestone / plan scope'}</div>
      <div class="release-meta"><span>${row.blockers} blockers</span><span>${ci}</span><span>${due}</span><span>${last}</span></div>
    </article>`;
  }).join('') || '<p class="outcome-empty">呢個 scope 未有 repo。</p>';
}

function renderRoadmap(items) {
  const shown = items.slice(0, 12);
  $('productRoadmap').innerHTML = shown.map((item) => {
    const pct = item.total ? (item.done / item.total) * 100 : 0;
    return `<div class="roadmap-row">
      <div class="roadmap-label"><strong>${esc(item.title)}</strong><span>${esc(item.repo.split('/').pop())} · ${item.source}</span></div>
      <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:#5F8CC6"></span></span>
      <span class="roadmap-value">${item.done}/${item.total}${item.due ? ` · ${esc(item.due)}` : ''}</span>
    </div>`;
  }).join('') || '<p class="outcome-empty">未有 milestones 或 plan sections。</p>';
  $('productRoadmapNote').textContent = items.length > shown.length ? `顯示 ${shown.length} / ${items.length}` : `${items.length} 個 epic`;
}

function outcomeCard(repo, metric, updatedAt) {
  const change = typeof metric.change === 'number' ? metric.change : null;
  const lowerIsBetter = metric.direction === 'down';
  const good = change == null ? null : lowerIsBetter ? change <= 0 : change >= 0;
  const sign = change != null && change > 0 ? '+' : '';
  const target = metric.target == null ? '' : `<span>目標 ${esc(number(metric.target))}${esc(metric.unit || '')}</span>`;
  return `<article class="outcome-metric">
    <div class="outcome-label">${esc(metric.label)}</div>
    <div class="outcome-value">${esc(number(metric.value))}<span>${esc(metric.unit || '')}</span></div>
    <div class="outcome-meta"><span>${esc(repo.split('/').pop())}</span>${target}
      ${change == null ? '' : `<span class="${good ? 'outcome-good' : 'outcome-bad'}">${sign}${change.toFixed(1)}%</span>`}
      ${updatedAt ? `<span>updated ${esc(updatedAt.slice(0, 10))}</span>` : ''}
    </div>
    ${metric.note ? `<p>${esc(metric.note)}</p>` : ''}
  </article>`;
}

function renderOutcomeGroup(id, repos, key) {
  const rm = state.data.repo_meta || {};
  const cards = [];
  for (const repo of repos) {
    const outcomes = (rm[repo] || {}).outcomes;
    for (const metric of outcomes?.[key] || []) cards.push(outcomeCard(repo, metric, outcomes.updated_at));
  }
  $(id).innerHTML = cards.join('') || `<p class="outcome-empty">未接通 ${key === 'adoption' ? '產品採用' : '客戶成果'}數據。設定 outcomes_file 後會喺呢度顯示。</p>`;
}

export function renderProductOutcomes() {
  const repos = scopedRepos();
  const tasks = windowTasks({ allPeople: true });
  const today = state.data.generated_at.slice(0, 10);
  const rows = repos.map((repo) => readinessForRepo(repo, tasks, today));
  const items = roadmapItems(repos);
  const end = refDate().getTime() + 864e5;
  const from = end - state.windowDays * 864e5;
  const shipped = repos.reduce((sum, repo) =>
    sum + releaseEventsInWindow((state.data.repo_meta || {})[repo] || {}, from, end).length, 0);
  const withOutcomes = repos.filter((repo) => (state.data.repo_meta || {})[repo]?.outcomes).length;
  $('productEpicTotal').textContent = items.length.toLocaleString();
  $('productReleaseCount').textContent = shipped.toLocaleString();
  $('productReadyCount').textContent = `${rows.filter((r) => r.status === 'ready').length}/${rows.filter((r) => r.scope).length}`;
  $('productOutcomeCoverage').textContent = repos.length ? `${withOutcomes}/${repos.length}` : '–';
  renderReadiness(rows);
  renderRoadmap(items);
  renderOutcomeGroup('adoptionMetrics', repos, 'adoption');
  renderOutcomeGroup('customerMetrics', repos, 'customer');
}
