import { state, $, esc, repoInScope, windowTasks } from './data.js';
import { deriveManagement } from './management.js?v=i18n-20260922-1';
import { stalenessMessage } from './staleness.js?v=i18n-20260922-1';
import { t, LOCALE } from './i18n/index.js?v=i18n-20260922-1';

const STATUS = {
  'on-track': { label: t('management.status.onTrack'), cls: 'is-good' },
  'at-risk': { label: t('management.status.atRisk'), cls: 'is-warn' },
  'off-track': { label: t('management.status.offTrack'), cls: 'is-bad' },
  unknown: { label: t('management.status.unknown'), cls: 'is-unknown' },
};
const HEALTH = {
  healthy: [t('management.health.healthy'), 'is-good'],
  attention: [t('management.health.attention'), 'is-warn'],
  stale: [t('management.health.stale'), 'is-bad'],
  unreadable: [t('management.health.unreadable'), 'is-unknown'],
  future: [t('management.health.future'), 'is-bad'],
  unknown: [t('management.health.unknown'), 'is-unknown'],
};
const CONFIDENCE = {
  actual: t('management.confidence.actual'),
  high: t('management.confidence.high'),
  medium: t('management.confidence.medium'),
  low: t('management.confidence.low'),
};
const FORECAST_REASON = {
  'no-plan': t('management.forecastReason.noPlan'),
  'not-enough-history': t('management.forecastReason.notEnoughHistory'),
  'history-too-short': t('management.forecastReason.historyTooShort'),
  'no-observed-progress': t('management.forecastReason.noObservedProgress'),
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
  if (counts['off-track']) parts.push(t('management.headline.countOffTrack', { n: counts['off-track'] }));
  if (counts['at-risk']) parts.push(t('management.headline.countAtRisk', { n: counts['at-risk'] }));
  if (counts.unknown) parts.push(t('management.headline.countUnknown', { n: counts.unknown }));
  if (!parts.length) parts.push(t('management.headline.countOnTrack', { n: counts['on-track'] }));
  setMetric('managementStatus', meta.label, parts.join(' · '), meta.cls);

  const [healthLabel, healthCls] = HEALTH[summary.health.status] || HEALTH.unknown;
  const c = summary.health.counts;
  setMetric('managementHealth', healthLabel,
    [
      t('management.headline.planningRatio', { planning: c.planning, repos: c.repos }),
      t('management.headline.historyRatio', { planHistory: c.planHistory, repos: c.repos }),
      t('management.headline.errorsCount', { n: c.issueErrors + c.repoErrors }),
    ].join(' · '),
    healthCls);

  const scopeValue = summary.totals.scopeRepos
    ? summary.totals.currentScope.toLocaleString(LOCALE) : '–';
  const net = summary.totals.net;
  const netLabel = net === 0
    ? t('management.scope.noNetChange')
    : t('management.scope.netChange', { net: `${net > 0 ? '+' : ''}${net}` });
  setMetric('managementScope', scopeValue,
    summary.totals.historyRepos
      ? [
          netLabel,
          t('management.scope.added', { n: summary.totals.added }),
          t('management.scope.removed', { n: summary.totals.removed }),
          t('management.scope.historyRatio',
            { historyRepos: summary.totals.historyRepos, scopeRepos: summary.totals.scopeRepos }),
        ].join(' · ')
      : summary.totals.scopeRepos
        ? `${t('management.scope.planCount', { n: summary.totals.scopeRepos })} · ${t('management.scope.noHistory')}`
      : t('management.scope.noPlanHistory'), summary.totals.scopeRepos ? '' : 'is-unknown');

  setMetric('managementForecast', `${summary.totals.forecastable}/${summary.totals.planning}`,
    summary.totals.planning
      ? `${t('management.forecast.lateCount', { n: summary.totals.forecastLate })} · ${t('management.forecast.reposWithScope')}`
      : t('management.forecast.noScope'), summary.totals.forecastable ? '' : 'is-unknown');
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
  }).join('') || `<li class="management-empty">${t('management.attention.empty')}</li>`;
}

function forecastText(forecast) {
  if (forecast.status === 'complete') return t('management.forecast.complete');
  if (forecast.status !== 'forecast') return FORECAST_REASON[forecast.reason] || t('management.forecast.unavailable');
  return t('management.forecast.projected', {
    date: forecast.projected,
    confidence: CONFIDENCE[forecast.confidence] || forecast.confidence,
  }) + (forecast.late ? t('management.forecast.lateSuffix') : '');
}

function renderProjects(projects) {
  $('managementProjects').innerHTML = projects.map((project) => {
    const meta = STATUS[project.status];
    const name = esc(project.repo.split('/').pop());
    const title = project.url
      ? `<a href="${esc(project.url)}" target="_blank" rel="noopener">${name}</a>` : name;
    const progress = project.progress == null ? '–' : `${project.progress.toFixed(0)}%`;
    const change = project.scopeChange?.available
      ? t('management.project.scopeChange',
          { net: `${project.scopeChange.net >= 0 ? '+' : ''}${project.scopeChange.net}` })
      : t('management.scope.noHistory');
    const reason = project.reasons.length ? project.reasons.join(' · ') : t('management.project.noKnownRisk');
    return `<article class="management-project ${meta.cls}">
      <div class="management-project-head"><span class="management-dot"></span>
        <strong>${title}</strong><span>${meta.label}</span></div>
      <div class="management-project-grid">
        <span>${project.scope ? `${esc(project.scope.title)} · ${progress}` : t('management.forecast.noScope')}</span>
        <span>${esc(forecastText(project.forecast))}</span>
        <span>${esc(change)}</span>
      </div>
      <small>${esc(reason)}${project.owner ? t('management.project.ownerSuffix', { owner: esc(project.owner) }) : ''}</small>
    </article>`;
  }).join('') || `<p class="management-empty">${t('management.project.emptyScope')}</p>`;
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
