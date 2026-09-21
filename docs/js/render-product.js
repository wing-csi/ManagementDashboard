import { state, $, esc, refDate, repoInScope, toDate, windowTasks } from './data.js';
import { t } from './i18n/index.js?v=i18n-20260922-1';

const BLOCKER_RE = /^(p0|critical|blocker|urgent|priority:\s*(urgent|highest))$/i;
// Built once at module evaluation — see docs/js/render-table.js TYPE_LABEL
// for why a static object (not a live getter) is correct here.
const READINESS = {
  ready: { label: t('product.readiness.ready'), color: 'var(--good)' },
  'on-track': { label: t('product.readiness.onTrack'), color: '#5F8CC6' },
  watch: { label: t('product.readiness.watch'), color: 'var(--warn)' },
  'at-risk': { label: t('product.readiness.atRisk'), color: 'var(--alert)' },
  unavailable: { label: t('product.readiness.unavailable'), color: '#9AA5A0' },
};
const SOURCE_LABEL = { milestone: t('product.sourceLabel.milestone'), plan: t('product.sourceLabel.plan') };

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
      ? { title: plan.path || t('product.sourceLabel.plan'), done: plan.done || 0, total: plan.total,
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
    const ci = row.ciPass == null ? t('product.noCiData') : t('product.ciValue', { value: row.ciPass.toFixed(0) });
    const due = row.scope?.due ? t('product.dueLabel', { due: row.scope.due }) : t('product.noDueDate');
    const last = row.lastRelease ? t('product.lastReleaseLabel', { date: row.lastRelease }) : t('product.noReleaseHistory');
    return `<article class="release-row">
      <div class="release-title"><span class="readiness-dot" style="background:${meta.color}"></span>
        <strong>${esc(row.repo.split('/').pop())}</strong><span class="readiness-state">${esc(meta.label)}</span></div>
      <div class="release-scope">${row.scope ? `${esc(row.scope.title)} · ${progress}` : esc(t('product.noScope'))}</div>
      <div class="release-meta"><span>${esc(t('product.blockerCount', { n: row.blockers }))}</span><span>${esc(ci)}</span><span>${esc(due)}</span><span>${esc(last)}</span></div>
    </article>`;
  }).join('') || `<p class="outcome-empty">${esc(t('product.readinessEmpty'))}</p>`;
}

function renderRoadmap(items) {
  const shown = items.slice(0, 12);
  $('productRoadmap').innerHTML = shown.map((item) => {
    const pct = item.total ? (item.done / item.total) * 100 : 0;
    return `<div class="roadmap-row">
      <div class="roadmap-label"><strong>${esc(item.title)}</strong><span>${esc(item.repo.split('/').pop())} · ${esc(SOURCE_LABEL[item.source] || item.source)}</span></div>
      <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:#5F8CC6"></span></span>
      <span class="roadmap-value">${item.done}/${item.total}${item.due ? ` · ${esc(item.due)}` : ''}</span>
    </div>`;
  }).join('') || `<p class="outcome-empty">${esc(t('product.roadmapEmpty'))}</p>`;
  $('productRoadmapNote').textContent = items.length > shown.length
    ? t('product.roadmapShown', { shown: shown.length, total: items.length })
    : t('product.roadmapCount', { n: items.length });
}

/** Flattens each in-scope repo's adoption + customer outcome entries into
 * one list. `item.key` indexes docs/js/i18n/dict/{zh,en}/product.js under
 * `outcomes.<key>` for both the label and the value's unit template — see
 * docs/data/demo-outcomes.js for why label/unit never get built by string
 * concatenation here. */
function outcomeRows(repos) {
  const rm = state.data.repo_meta || {};
  const rows = [];
  for (const repo of repos) {
    const outcomes = rm[repo]?.outcomes;
    if (!outcomes) continue;
    for (const item of [...(outcomes.adoption || []), ...(outcomes.customer || [])]) {
      rows.push({ repo, ...item });
    }
  }
  return rows;
}

/* item.key arrives from a repo-committed outcomes file — the same trust tier as
   plan.md — and is spliced into a dotted dictionary path. Restricting it to a
   plain identifier keeps a crafted key (`__proto__`, `constructor`) out of the
   lookup walk entirely, rather than relying on that walk staying read-only. */
const OUTCOME_KEY_RE = /^[A-Za-z0-9_]+$/;

function outcomeRowHTML(item) {
  const key = OUTCOME_KEY_RE.test(item.key || '') ? item.key : null;
  const label = key ? t(`product.outcomes.${key}.label`) : String(item.key ?? '');
  const value = key
    ? t(`product.outcomes.${key}.unit`, { value: item.value, n: item.value })
    : String(item.value ?? '');
  return `<div class="roadmap-row">
    <div class="roadmap-label"><strong title="${esc(label)}">${esc(label)}</strong><span>${esc(item.repo.split('/').pop())}</span></div>
    <span class="roadmap-value">${esc(value)}</span>
  </div>`;
}

/** Mounted once as a sibling of .product-duo, inside #panel-product — the
 * outcomes fixture (docs/data/demo-outcomes.js) has no static container in
 * docs/index.html, and that file is out of scope for this module. Idempotent:
 * re-render() calls (filter changes) update the existing container in place
 * rather than appending a duplicate. */
function renderOutcomes(repos) {
  let section = $('productOutcomes');
  if (!section) {
    section = document.createElement('section');
    section.className = 'card';
    section.id = 'productOutcomes';
    section.innerHTML = '<div class="card-head"><h2 id="productOutcomesTitle"></h2></div>'
      + '<div id="productOutcomesBody"></div>';
    document.querySelector('#panel-product .product-duo')?.after(section);
  }
  const titleEl = section.querySelector('#productOutcomesTitle');
  if (titleEl) titleEl.textContent = t('product.outcomesTitle');
  const bodyEl = section.querySelector('#productOutcomesBody');
  if (!bodyEl) return;
  const rows = outcomeRows(repos);
  bodyEl.innerHTML = rows.length
    ? rows.map(outcomeRowHTML).join('')
    : `<p class="outcome-empty">${esc(t('product.outcomesEmpty'))}</p>`;
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
  renderOutcomes(repos);
}
