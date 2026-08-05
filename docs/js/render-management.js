import { state, $, esc, repoInScope, windowTasks } from './data.js';
import { deriveManagement } from './management.js?v=zh-20260805-3';
import { stalenessMessage } from './staleness.js?v=zh-20260805-3';

const STATUS = {
  'on-track': { label: '進度正常', cls: 'is-good' },
  'at-risk': { label: '存在風險', cls: 'is-warn' },
  'off-track': { label: '偏離計劃', cls: 'is-bad' },
  unknown: { label: '未知', cls: 'is-unknown' },
};
const HEALTH = {
  healthy: ['最新', 'is-good'], attention: ['需要關注', 'is-warn'],
  stale: ['已過時', 'is-bad'], unreadable: ['未知', 'is-unknown'],
  future: ['時鐘不一致', 'is-bad'], unknown: ['未知', 'is-unknown'],
};
const CONFIDENCE = { actual: '實際', high: '高', medium: '中', low: '低' };
const FORECAST_REASON = {
  'no-plan': '未有計劃', 'not-enough-history': '觀測點不足',
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
  if (counts['off-track']) parts.push(`${counts['off-track']} 個偏離計劃`);
  if (counts['at-risk']) parts.push(`${counts['at-risk']} 個存在風險`);
  if (counts.unknown) parts.push(`${counts.unknown} 個未知`);
  if (!parts.length) parts.push(`${counts['on-track']} 個進度正常`);
  setMetric('managementStatus', meta.label, parts.join(' · '), meta.cls);

  const [healthLabel, healthCls] = HEALTH[summary.health.status] || HEALTH.unknown;
  const c = summary.health.counts;
  setMetric('managementHealth', healthLabel,
    `${c.planning}/${c.repos} 有計劃 · ${c.planHistory}/${c.repos} 有歷史 · ${c.issueErrors + c.repoErrors} 個錯誤`,
    healthCls);

  const scopeValue = summary.totals.scopeRepos
    ? summary.totals.currentScope.toLocaleString() : '–';
  const net = summary.totals.net;
  const netLabel = net === 0 ? '範圍無淨變動' : `範圍淨變動 ${net > 0 ? '+' : ''}${net}`;
  setMetric('managementScope', scopeValue,
    summary.totals.historyRepos
      ? `${netLabel} · 新增 ${summary.totals.added} · 移除 ${summary.totals.removed} · ${summary.totals.historyRepos}/${summary.totals.scopeRepos} 有歷史`
      : summary.totals.scopeRepos
        ? `${summary.totals.scopeRepos} 個計劃 · 無範圍歷史`
      : '未有計劃歷史', summary.totals.scopeRepos ? '' : 'is-unknown');

  setMetric('managementForecast', `${summary.totals.forecastable}/${summary.totals.planning}`,
    summary.totals.planning
      ? `${summary.totals.forecastLate} 個預測延誤 · 有計劃範圍的程式庫`
      : '未有計劃範圍', summary.totals.forecastable ? '' : 'is-unknown');
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
  return `預測 ${forecast.projected} · ${CONFIDENCE[forecast.confidence] || forecast.confidence}信心`
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
      ? `範圍 ${project.scopeChange.net >= 0 ? '+' : ''}${project.scopeChange.net}`
      : '無範圍歷史';
    const reason = project.reasons.length ? project.reasons.join(' · ') : '冇已知風險';
    return `<article class="management-project ${meta.cls}">
      <div class="management-project-head"><span class="management-dot"></span>
        <strong>${title}</strong><span>${meta.label}</span></div>
      <div class="management-project-grid">
        <span>${project.scope ? `${esc(project.scope.title)} · ${progress}` : '未有計劃範圍'}</span>
        <span>${esc(forecastText(project.forecast))}</span>
        <span>${esc(change)}</span>
      </div>
      <small>${esc(reason)}${project.owner ? ` · 負責人 ${esc(project.owner)}` : ''}</small>
    </article>`;
  }).join('') || '<p class="management-empty">此範圍內沒有程式庫。</p>';
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
