import { state, $, esc, refDate, repoInScope, toDate, windowTasks } from './data.js';

const BLOCKER_RE = /^(p0|critical|blocker|urgent|priority:\s*(urgent|highest))$/i;
const READINESS = {
  ready: { label: '已準備', color: 'var(--good)' },
  'on-track': { label: '進度正常', color: '#5F8CC6' },
  watch: { label: '需要留意', color: 'var(--warn)' },
  'at-risk': { label: '存在風險', color: 'var(--alert)' },
  unavailable: { label: '未有範圍', color: '#9AA5A0' },
};
const SOURCE_LABEL = { milestone: '里程碑', plan: '計劃' };

const scopedRepos = () => (state.data.repos || []).filter(repoInScope);
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
      ? { title: plan.path || '計劃', done: plan.done || 0, total: plan.total,
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
    const due = row.scope?.due ? `期限 ${row.scope.due}` : '未設期限';
    const last = row.lastRelease ? `上次發佈 ${row.lastRelease}` : '未有發佈記錄';
    return `<article class="release-row">
      <div class="release-title"><span class="readiness-dot" style="background:${meta.color}"></span>
        <strong>${esc(row.repo.split('/').pop())}</strong><span class="readiness-state">${meta.label}</span></div>
      <div class="release-scope">${row.scope ? `${esc(row.scope.title)} · ${progress}` : '未有里程碑 / 計劃範圍'}</div>
      <div class="release-meta"><span>${row.blockers} 個阻礙項目</span><span>${ci}</span><span>${due}</span><span>${last}</span></div>
    </article>`;
  }).join('') || '<p class="outcome-empty">此範圍內沒有程式庫。</p>';
}

function renderRoadmap(items) {
  const shown = items.slice(0, 12);
  $('productRoadmap').innerHTML = shown.map((item) => {
    const pct = item.total ? (item.done / item.total) * 100 : 0;
    return `<div class="roadmap-row">
      <div class="roadmap-label"><strong>${esc(item.title)}</strong><span>${esc(item.repo.split('/').pop())} · ${SOURCE_LABEL[item.source] || item.source}</span></div>
      <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:#5F8CC6"></span></span>
      <span class="roadmap-value">${item.done}/${item.total}${item.due ? ` · ${esc(item.due)}` : ''}</span>
    </div>`;
  }).join('') || '<p class="outcome-empty">未有里程碑或計劃分段。</p>';
  $('productRoadmapNote').textContent = items.length > shown.length ? `顯示 ${shown.length} / ${items.length}` : `${items.length} 個大型工作項`;
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
}
