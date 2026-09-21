import { state, $, esc, toDate, repoInScope, registerUrl } from './data.js';
import { issuesInScope } from './aggregate.js?v=i18n-20260922-1';
import { t } from './i18n/index.js?v=i18n-20260922-1';

const PRIORITY_RE = [
  [/^(p0|priority: ?(urgent|highest)|urgent|critical|blocker)$/i, 40, t('project.priority.p0')],
  [/^(p1|priority: ?high|high)$/i, 25, t('project.priority.high')],
  [/^(p2|priority: ?medium|medium)$/i, 10, t('project.priority.medium')],
];
export function issueScore(iss, todayStr) {
  let sc = 0;
  const why = [];
  const today = toDate(todayStr);
  if (iss.due) {
    const overdue = Math.round((today - toDate(iss.due)) / 864e5);
    if (overdue > 0) { sc += overdue * 3; why.push(t('project.overdueDays', { n: overdue })); }
  }
  for (const l of iss.labels || []) {
    for (const [re, w, label] of PRIORITY_RE) if (re.test(l)) { sc += w; why.push(label); }
    if (/^bug$/i.test(l)) { sc += 15; why.push(t('project.labels.bug')); }
  }
  if (iss.created) {
    const age = Math.round((today - toDate(iss.created)) / 864e5);
    if (age > 0) { sc += Math.min(60, age) * 0.3; why.push(t('project.openDays', { n: age })); }
  }
  return { sc, why };
}

export function renderProjects() {
  const today = state.data.generated_at.slice(0, 10);
  const scope = issuesInScope();
  const chips = $('projChips');
  chips.innerHTML = '';
  const rm = state.data.repo_meta || {};
  for (const repo of (state.data.repos || [])) {
    if (!repoInScope(repo)) continue;
    const iss = (rm[repo] || {}).issues;
    const plan = (rm[repo] || {}).plan;
    const owner = (rm[repo] || {}).owner;
    const ownerBit = ` <span style="color:var(--muted)">${t('project.chip.owner', { owner: esc(owner || t('project.chip.unspecifiedOwner')) })}</span>`;
    const el = document.createElement('span');
    el.className = 'chip-rag';
    if (plan && plan.total) {
      const hasIss = iss && (iss.open_total + iss.closed_total) > 0;
      const overdueN = hasIss ? (iss.open || []).filter((i) => i.due && i.due < today).length : 0;
      const dotColor = hasIss ? (overdueN > 0 ? 'var(--alert)' : '#2E7D4F') : '#5F8CC6';
      el.title = t('project.chip.tooltipSourceLabel', { path: plan.path, done: plan.done, total: plan.total })
        + (hasIss ? t('project.chip.tooltipWithIssues') : t('project.chip.tooltipWithoutIssues'));
      el.innerHTML = `<span class="dotg" style="background:${dotColor}"></span>${esc(repo.split('/').pop())} <span style="color:var(--muted)">${t('project.chip.completionPlan', { pct: ((plan.done / plan.total) * 100).toFixed(0), done: plan.done, total: plan.total })}</span>${ownerBit}`;
      chips.appendChild(el);
      continue;
    }
    if (!iss || (iss.open_total + iss.closed_total) === 0) {
      el.innerHTML = `<span class="dotg" style="background:#9AA5A0"></span>${esc(repo.split('/').pop())} <span style="color:var(--muted)">${t('project.chip.noIssuesOrPlan')}</span>${ownerBit}`;
    } else {
      const done = iss.closed_total, total = iss.open_total + iss.closed_total;
      const overdueN = (iss.open || []).filter((i) => i.due && i.due < today).length;
      const staleN = (iss.open || []).filter((i) => (toDate(today) - toDate(i.updated)) / 864e5 > 14).length;
      const risk = overdueN > 0 ? ['var(--alert)', t('project.risk.high')]
        : (iss.open_total && staleN / iss.open_total >= 0.3) ? ['var(--warn)', t('project.risk.medium')]
        : ['#2E7D4F', t('project.risk.normal')];
      el.title = t('project.chip.issueTooltip', { done, open: iss.open_total, overdue: overdueN, stale: staleN });
      el.innerHTML = `<span class="dotg" style="background:${risk[0]}"></span>${esc(repo.split('/').pop())} <span style="color:var(--muted)">${t('project.chip.completionIssues', { pct: ((done / total) * 100).toFixed(0), done, total, risk: risk[1] })}</span>${ownerBit}`;
    }
    chips.appendChild(el);
  }

  const msBox = $('projMilestones');
  msBox.innerHTML = '';
  for (const ms of scope.milestones) {
    const total = ms.open + ms.closed;
    const pctDone = total ? (ms.closed / total) * 100 : 0;
    const late = ms.due && ms.due < today;
    const row = document.createElement('div');
    row.className = 'ms-row';
    row.innerHTML = `<span class="t" title="${esc(ms.title)}">${esc(ms.title)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${pctDone}%;background:${late ? 'var(--alert)' : '#5F8CC6'}"></span></span>
      <span class="p">${ms.closed}/${total}${ms.due ? `${t('project.milestone.due', { due: ms.due.slice(5) })}${late ? ' ⚠' : ''}` : ''}</span>`;
    msBox.appendChild(row);
  }
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const plan = m.plan;
    if (!plan || !plan.sections) continue;
    for (const s of plan.sections) {
      const pctDone = s.total ? (s.done / s.total) * 100 : 0;
      const row = document.createElement('div');
      row.className = 'ms-row';
      row.innerHTML = `<span class="t" title="${esc(t('project.milestone.sectionTooltip', { title: s.title, path: plan.path }))}">${esc(s.title)} <span style="color:var(--muted)">· ${t('project.milestone.planLabel')}</span></span>
        <span class="bar-track"><span class="bar-fill" style="width:${pctDone}%;background:#8FA8CB"></span></span>
        <span class="p">${s.done}/${s.total}</span>`;
      msBox.appendChild(row);
    }
  }

  const planItems = [];
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const plan = m.plan;
    if (!plan || !plan.open_tasks) continue;
    for (const task of plan.open_tasks) {
      planItems.push({
        number: null, title: task.title,
        url: registerUrl(repo, plan),
        labels: [...(task.priority ? [task.priority] : []), ...(task.bug ? ['bug'] : [])],
        milestone: task.section, due: task.due || null, created: null, updated: null, repo,
      });
    }
  }
  const pool = scope.open.concat(planItems);

  const lateBox = $('projLate');
  const todoBox = $('projTodo');
  lateBox.innerHTML = '';
  todoBox.innerHTML = '';
  if (!pool.length && !(scope.openTotal + scope.closedTotal)) {
    lateBox.innerHTML = `<li class="empty">${t('project.empty.noPlanningData')}</li>`;
    todoBox.innerHTML = '<li class="empty">–</li>';
    return;
  }
  const item = (i, extra) => `<li><span><a class="tlink" href="${esc(i.url)}" target="_blank" rel="noopener">${i.number ? '#' + i.number : t('project.milestone.planLabel')}</a> ${esc(i.title)}</span><span class="meta">${extra}</span></li>`;
  const abnormal = pool
    .map((i) => {
      const over = i.due && i.due < today ? Math.round((toDate(today) - toDate(i.due)) / 864e5) : 0;
      const stale = i.updated ? Math.round((toDate(today) - toDate(i.updated)) / 864e5) : 0;
      return { i, over, stale };
    })
    .filter((x) => x.over > 0 || x.stale > 14)
    .sort((a, b) => b.over - a.over || b.stale - a.stale)
    .slice(0, 6);
  lateBox.innerHTML = abnormal.length
    ? abnormal.map((x) => item(x.i, x.over > 0
        ? `<span class="late">${t('project.overdueDays', { n: x.over })}</span>`
        : t('project.late.staleDays', { n: x.stale }))).join('')
    : `<li class="empty">${t('project.empty.noLateWork')}</li>`;
  const todo = [...pool].sort((a, b) => issueScore(b, today).sc - issueScore(a, today).sc).slice(0, 5);
  todoBox.innerHTML = todo.length
    ? todo.map((i) => item(i, (i.labels || []).slice(0, 2).join(' · ') || (i.milestone || ''))).join('')
    : `<li class="empty">${t('project.empty.noTodoWork')}</li>`;
}
