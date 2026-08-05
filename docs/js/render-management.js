import { state, $, esc, repoInScope, windowTasks } from './data.js';
import { deriveManagement } from './management.js';
import { stalenessMessage } from './staleness.js';

const STATUS = {
  'on-track': { label: 'On track', cls: 'is-good' },
  'at-risk': { label: 'At risk', cls: 'is-warn' },
  'off-track': { label: 'Off track', cls: 'is-bad' },
  unknown: { label: 'Unknown', cls: 'is-unknown' },
};
const HEALTH = {
  healthy: ['Fresh', 'is-good'], attention: ['Needs attention', 'is-warn'],
  stale: ['Stale', 'is-bad'], unreadable: ['Unknown', 'is-unknown'],
  future: ['Clock mismatch', 'is-bad'], unknown: ['Unknown', 'is-unknown'],
};
const FORECAST_REASON = {
  'no-plan': '未有 plan', 'not-enough-history': '觀測點不足',
  'history-too-short': '歷史少過 7 日', 'no-observed-progress': '未觀測到完成進度',
};

function setMetric(id, value, sub, cls = '') {
  const el = $(id);
  el.textContent = value;
  el.className = `value management-value ${cls}`.trim();
  $(`${id}Sub`).textContent = sub;
}

function renderStaleBanner(summary) {
  const banner = $('staleBanner');
  if (!banner || state.demo || summary.health.freshness.status === 'fresh') {
    if (banner) banner.hidden = true;
    return;
  }
  banner.textContent = stalenessMessage(summary.health.freshness);
  banner.className = `stale-banner is-${summary.health.freshness.status}`;
  banner.hidden = false;
}

function renderHeadline(summary) {
  const meta = STATUS[summary.portfolioStatus];
  const counts = Object.fromEntries(Object.keys(STATUS).map((key) => [key, 0]));
  for (const project of summary.projects) counts[project.status]++;
  const parts = [];
  if (counts['off-track']) parts.push(`${counts['off-track']} off track`);
  if (counts['at-risk']) parts.push(`${counts['at-risk']} at risk`);
  if (counts.unknown) parts.push(`${counts.unknown} unknown`);
  if (!parts.length) parts.push(`${counts['on-track']} on track`);
  setMetric('managementStatus', meta.label, parts.join(' · '), meta.cls);

  const [healthLabel, healthCls] = HEALTH[summary.health.status] || HEALTH.unknown;
  const c = summary.health.counts;
  setMetric('managementHealth', healthLabel,
    `${c.planning}/${c.repos} planning · ${c.planHistory}/${c.repos} history · ${c.issueErrors + c.repoErrors} errors`,
    healthCls);

  const scopeValue = summary.totals.scopeRepos
    ? summary.totals.currentScope.toLocaleString() : '–';
  const net = summary.totals.net;
  const netLabel = net === 0 ? 'scope 無淨變動' : `${net > 0 ? '+' : ''}${net} net scope`;
  setMetric('managementScope', scopeValue,
    summary.totals.historyRepos
      ? `${netLabel} · +${summary.totals.added} added · −${summary.totals.removed} removed · ${summary.totals.historyRepos}/${summary.totals.scopeRepos} histories`
      : summary.totals.scopeRepos
        ? `${summary.totals.scopeRepos} plans · scope history unavailable`
      : '未有 plan history', summary.totals.scopeRepos ? '' : 'is-unknown');

  setMetric('managementForecast', `${summary.totals.forecastable}/${summary.totals.planning}`,
    summary.totals.planning
      ? `${summary.totals.forecastLate} projected late · 有 planning scope 嘅 repo`
      : '未有 planning scope', summary.totals.forecastable ? '' : 'is-unknown');
}

function renderAttention(items) {
  $('managementAttention').innerHTML = items.map((item) => {
    const title = item.url
      ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>`
      : esc(item.title);
    return `<li class="attention-${item.severity}">
      <span class="attention-sig"></span>
      <span><strong>${title}</strong><small>${esc(item.detail)}</small></span>
    </li>`;
  }).join('') || '<li class="management-empty">目前冇需要即時跟進嘅已知項目。</li>';
}

function forecastText(forecast) {
  if (forecast.status === 'complete') return '已完成';
  if (forecast.status !== 'forecast') return FORECAST_REASON[forecast.reason] || '預測不可用';
  return `預測 ${forecast.projected} · ${forecast.confidence} confidence`
    + (forecast.late ? ' · 遲過目標日' : '');
}

function renderProjects(projects) {
  $('managementProjects').innerHTML = projects.map((project) => {
    const meta = STATUS[project.status];
    const name = esc(project.repo.split('/').pop());
    const title = project.url
      ? `<a href="${esc(project.url)}" target="_blank" rel="noopener">${name}</a>` : name;
    const progress = project.progress == null ? '–' : `${project.progress.toFixed(0)}%`;
    const change = project.scopeChange?.available
      ? `${project.scopeChange.net >= 0 ? '+' : ''}${project.scopeChange.net} scope`
      : 'scope history unavailable';
    const reason = project.reasons.length ? project.reasons.join(' · ') : '冇已知風險';
    return `<article class="management-project ${meta.cls}">
      <div class="management-project-head"><span class="management-dot"></span>
        <strong>${title}</strong><span>${meta.label}</span></div>
      <div class="management-project-grid">
        <span>${project.scope ? `${esc(project.scope.title)} · ${progress}` : '未有 planning scope'}</span>
        <span>${esc(forecastText(project.forecast))}</span>
        <span>${esc(change)}</span>
      </div>
      <small>${esc(reason)}${project.owner ? ` · owner ${esc(project.owner)}` : ''}</small>
    </article>`;
  }).join('') || '<p class="management-empty">呢個 scope 冇 repo。</p>';
}

export function renderManagement() {
  const repos = (state.data.repos || []).filter(repoInScope);
  const tasks = windowTasks({ allPeople: true });
  const summary = deriveManagement(state.data, {
    repos, tasks, todayStr: state.data.generated_at.slice(0, 10), nowMs: Date.now(),
  });
  renderStaleBanner(summary);
  renderHeadline(summary);
  renderAttention(summary.attention);
  renderProjects(summary.projects);
}
