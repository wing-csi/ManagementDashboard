import { state, $, esc, repoInScope } from './data.js';
import { burndownSeries } from './burndown.js?v=i18n-20260922-1';
import { timelineHTML } from './render-timeline.js?v=i18n-20260922-1';
import { timelineStrip } from './timeline.js';
import { completionForecast, scopeChange } from './management.js?v=i18n-20260922-1';
import { LANG, t } from './i18n/index.js?v=i18n-20260922-1';

/** 每個 repo 一個 Chart 實例。state.chart 得一個位,係每週圖嘅;
 *  唔另開一本帳,重畫嗰陣舊 canvas 會漏返出嚟。 */
const charts = new Map();

const CAPTION_KEY = {
  'single-point': 'caption.singlePoint',
};

/** 冇理想線嘅三個原因,逐個有自己嘅講法 —— 讀嘅人要知去改 plan.md 邊度。 */
const IDEAL_CAPTION_KEY = {
  'no-due': 'idealCaption.noDue',
  'due-unusable': 'idealCaption.dueUnusable',
  'due-not-after-start': 'idealCaption.dueNotAfterStart',
};

/** 條軸個起點由邊層話事。每次都出:同一條軸,由 repo 開檔拉起同由第一次
 *  改 plan.md 拉起,理想線同 SPI 嘅意思完全唔同,但畫面上一模一樣。 */
const START_CAPTION_KEY = {
  plan: 'startCaption.plan',
  repo: 'startCaption.repo',
  observation: 'startCaption.observation',
};

/** 宣告咗但用唔到嘅 start: —— 兩個原因要改嘅嘢唔同。冇宣告唔係一個錯,
 *  所以呢度冇第三個 key。 */
const START_REASON_CAPTION_KEY = {
  'start-unusable': 'startReasonCaption.startUnusable',
  'start-after-history': 'startReasonCaption.startAfterHistory',
};

const FORECAST_REASON_KEY = {
  'no-plan': 'forecastReason.noPlan',
  'not-enough-history': 'forecastReason.notEnoughHistory',
  'history-too-short': 'forecastReason.historyTooShort',
  'no-observed-progress': 'forecastReason.noObservedProgress',
};

const STATUS_LABEL_KEY = {
  complete: 'statusLabel.complete',
  'on-track': 'statusLabel.onTrack',
  'at-risk': 'statusLabel.atRisk',
  'off-track': 'statusLabel.offTrack',
  unknown: 'statusLabel.unknown',
};

const MONTH_ABBR_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Chinese renders `08/06`, which reads as either 8 June or 6 August — never
// safe on a projector. English spells the month out instead: `06 Aug`. Built
// by hand rather than via toLocaleDateString() so the day-then-month order
// is guaranteed regardless of the runtime's generic-'en' locale data.
const shortDate = (date) => {
  if (!date) return t('burndown.na');
  if (LANG === 'en') {
    const [, month, day] = date.split('-');
    return `${day} ${MONTH_ABBR_EN[Number(month) - 1]}`;
  }
  return date.slice(5).replace('-', '/');
};
const signed = (value) => `${value > 0 ? '+' : ''}${value}`;

function planUrl(repo, plan) {
  return `https://github.com/${repo}/blob/${plan.ref || 'HEAD'}/${plan.path}`;
}

/** 將圖上嘅訊號翻譯成 PM 可以直接作決定嘅五個數。
 *
 *  SPI 仍然保留做內部判斷,但唔再要求讀者識背公式。卡面直接講「今日應做
 *  幾多」同實際差幾多個百分點;scope 同 forecast 分開,避免將加 scope 誤讀
 *  成團隊突然做慢咗。 */
function managementSummary(plan, series, today) {
  const timeline = timelineStrip(plan, today);
  const scope = scopeChange(plan, today);
  const forecast = completionForecast(plan, today);
  const total = Math.max(0, Number(plan.total) || 0);
  const done = Math.min(total, Math.max(0, Number(plan.done) || 0));
  const remaining = Math.max(0, total - done);
  const progressPct = total ? done / total * 100 : null;

  let expectedPct = null;
  if (timeline.start && timeline.due && timeline.spiReason !== 'due-not-after-start') {
    const start = Date.parse(`${timeline.start}T00:00:00Z`);
    const due = Date.parse(`${timeline.due}T00:00:00Z`);
    const now = Date.parse(`${today}T00:00:00Z`);
    if (Number.isFinite(start) && Number.isFinite(due) && due > start) {
      expectedPct = Math.max(0, Math.min(100, (now - start) / (due - start) * 100));
    }
  }
  const gapPct = progressPct == null || expectedPct == null
    ? null : progressPct - expectedPct;
  const idealToday = series.todayIndex >= 0 ? series.ideal[series.todayIndex] : null;
  const idealRemaining = idealToday == null && timeline.daysLeft != null && timeline.daysLeft < 0
    ? 0 : idealToday;
  const remainingGap = idealRemaining == null ? null : remaining - idealRemaining;

  let status = 'unknown';
  if (total > 0 && remaining === 0) status = 'complete';
  else if ((timeline.daysLeft != null && timeline.daysLeft < 0)
           || (timeline.spi != null && timeline.spi < 0.8)) status = 'off-track';
  else if (timeline.overdue > 0 || (timeline.spi != null && timeline.spi < 1)
           || (forecast.status === 'forecast' && forecast.late)) status = 'at-risk';
  else if (timeline.spi != null) status = 'on-track';

  return {
    timeline, scope, forecast, total, done, remaining, progressPct,
    expectedPct, gapPct, remainingGap, status, backfilled: !!plan.history_backfilled,
  };
}

function metricHTML(label, value, detail, tone = '') {
  return `<div class="burn-metric ${tone}">
    <div class="burn-metric-label">${esc(label)}</div>
    <div class="burn-metric-value">${esc(value)}</div>
    <div class="burn-metric-detail">${esc(detail)}</div>
  </div>`;
}

function targetMetric(summary) {
  const { timeline } = summary;
  if (!timeline.due) {
    const reason = timeline.dueReason === 'due-unusable' ? t('burndown.target.dateInvalid')
      : timeline.dueReason === 'due-not-after-start' ? t('burndown.target.dueNotAfterStart')
        : t('burndown.target.notSet');
    return metricHTML(t('burndown.target.label'), t('burndown.na'), reason, 'is-unknown');
  }
  const detail = timeline.daysLeft == null ? t('burndown.target.cannotCompute')
    : timeline.daysLeft >= 0 ? t('burndown.target.daysLeft', { n: timeline.daysLeft })
      : t('burndown.target.overdueDays', { n: Math.abs(timeline.daysLeft) });
  return metricHTML(t('burndown.target.label'), shortDate(timeline.due), detail,
    timeline.daysLeft != null && timeline.daysLeft < 0 ? 'is-bad' : '');
}

function scopeMetric(summary) {
  const { scope } = summary;
  if (!scope.available) {
    return metricHTML(t('burndown.scope.label'), t('burndown.na'),
      t('burndown.scope.noBaseline'), 'is-unknown');
  }
  const tone = scope.net > 0 ? 'is-warn' : scope.net < 0 ? 'is-good' : '';
  const prefix = summary.backfilled && scope.baselineDate
    ? t('burndown.scope.sinceDate', { date: shortDate(scope.baselineDate) })
    : t('burndown.scope.fromStart');
  return metricHTML(t('burndown.scope.label'), signed(scope.net),
    t('burndown.scope.detail', { prefix, baseline: scope.baseline, current: scope.current }), tone);
}

function forecastMetric(summary) {
  const { forecast, timeline } = summary;
  if (forecast.status === 'complete') {
    return metricHTML(t('burndown.forecast.label'), t('burndown.forecast.completeValue'),
      t('burndown.forecast.actualResult'), 'is-good');
  }
  if (forecast.status !== 'forecast') {
    const reasonKey = FORECAST_REASON_KEY[forecast.reason];
    return metricHTML(t('burndown.forecast.label'), t('burndown.na'),
      reasonKey ? t(`burndown.${reasonKey}`) : t('burndown.forecast.unavailable'), 'is-unknown');
  }
  const confidenceText = forecast.confidence === 'high' ? t('burndown.forecast.confidenceHigh')
    : forecast.confidence === 'medium' ? t('burndown.forecast.confidenceMedium')
      : t('burndown.forecast.confidenceLow');
  let detail = t('burndown.forecast.rateDetail', { rate: forecast.ratePerWeek, confidence: confidenceText });
  if (timeline.due) {
    const delta = Math.round((Date.parse(`${forecast.projected}T00:00:00Z`)
      - Date.parse(`${timeline.due}T00:00:00Z`)) / 864e5);
    detail += delta > 0 ? t('burndown.forecast.late', { n: delta })
      : delta < 0 ? t('burndown.forecast.early', { n: Math.abs(delta) }) : t('burndown.forecast.onTime');
  }
  return metricHTML(t('burndown.forecast.label'), shortDate(forecast.projected), detail,
    forecast.late ? 'is-bad' : 'is-good');
}

function headlineHTML(summary) {
  const bits = [];
  if (summary.status === 'complete') {
    bits.push(t('burndown.headline.allComplete'));
  } else if (summary.gapPct != null) {
    const abs = Math.abs(Math.round(summary.gapPct));
    bits.push(summary.gapPct < 0
      ? t('burndown.headline.behind', { n: abs })
      : summary.gapPct > 0
        ? t('burndown.headline.ahead', { n: abs })
        : t('burndown.headline.onIdeal'));
  } else {
    bits.push(t('burndown.headline.insufficientData'));
  }
  if (summary.remainingGap != null && summary.remainingGap > 0) {
    bits.push(t('burndown.headline.aboveIdeal', { n: Math.ceil(summary.remainingGap) }));
  }
  if (summary.timeline.overdue > 0) {
    bits.push(t('burndown.headline.overdueCount', { n: summary.timeline.overdue }));
  }
  const statusKey = STATUS_LABEL_KEY[summary.status];
  return `<div class="burn-callout">
    <span class="burn-status is-${summary.status}">${esc(t(`burndown.${statusKey}`))}</span>
    <strong>${esc(bits.join(' · '))}</strong>
  </div>`;
}

function summaryHTML(plan, series, today) {
  const summary = managementSummary(plan, series, today);
  const progressValue = summary.progressPct == null ? t('burndown.na') : `${Math.round(summary.progressPct)}%`;
  const progressTone = summary.status === 'off-track' ? 'is-bad'
    : summary.status === 'at-risk' ? 'is-warn'
      : summary.status === 'complete' || summary.status === 'on-track' ? 'is-good' : 'is-unknown';
  return headlineHTML(summary)
    + '<div class="burn-metrics">'
    + metricHTML(t('burndown.summary.progressLabel'), progressValue,
      t('burndown.summary.progressDetail', { done: summary.done, total: summary.total }), progressTone)
    + metricHTML(t('burndown.summary.remainingLabel'), String(summary.remaining),
      t('burndown.summary.remainingDetail'))
    + targetMetric(summary)
    + scopeMetric(summary)
    + forecastMetric(summary)
    + '</div>';
}

/** 今日嗰條直線。Chart.js 4 冇內置 annotation,但一個 inline plugin
 *  就夠 —— 為咗一條線裝多個 CDN library 唔抵。
 *
 *  `chart.$todayMarkerDrawnIndex` 純粹俾測試用:讀 options.plugins.todayMarker
 *  淨係讀到設定咗乜,唔證明個 hook 真係行過 —— `new Chart(...)` 漏咗
 *  `plugins: [todayMarker]` 嗰陣,呢個 config namespace 照樣喺度,但條線
 *  唔會畫。留一個喺 hook 入面先至會寫嘅痕跡,先分得出「設定咗」同「真係畫咗」。 */
const todayMarker = {
  id: 'todayMarker',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts || opts.index == null || opts.index < 0) return;
    chart.$todayMarkerDrawnIndex = opts.index;
    const x = chart.scales.x.getPixelForValue(opts.index);
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = '#C4553B';
    ctx.lineWidth = 1;
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#C4553B';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(t('burndown.chart.todayLabel'), x, top - 3);
    ctx.restore();
  },
};

function captionFor(series, plan) {
  const bits = [];
  const captionKey = CAPTION_KEY[series.status];
  if (captionKey) bits.push(t(`burndown.${captionKey}`));
  const startCaptionKey = START_CAPTION_KEY[series.startSource];
  if (startCaptionKey) bits.push(t(`burndown.${startCaptionKey}`));
  const startReasonKey = START_REASON_CAPTION_KEY[series.startReason];
  if (startReasonKey) {
    bits.push(t(`burndown.${startReasonKey}`));
  }
  // 以前呢度睇 `!series.due`,即係「有冇死線」。但一個宣告咗、畫唔出嘅
  // 死線(早過或者啱啱等於第一個觀測)一樣係 `due` 有值 —— 結果係冇線
  // 又冇解釋,正正係 spec §7 唔准嘅嘢。改為問 burndownSeries 本人點解冇
  // 線:條線畫唔畫同呢句講唔講,由同一個 idealReason 話事。
  if (series.idealReason) {
    const idealKey = IDEAL_CAPTION_KEY[series.idealReason];
    bits.push(idealKey ? t(`burndown.${idealKey}`) : t('burndown.idealCaption.default'));
  }
  // 呢句淨係喺起點真係由「現存最早嗰個觀測」話事嗰陣先啱。起點由 start:
  // 或者 repo 開檔話事嘅時候,截斷咗嘅係中間嗰段觀測,唔係條理想線個錨 ——
  // 照出就係講錯嘢。
  if (series.truncated && series.startSource === 'observation') {
    bits.push(t('burndown.caption.truncated'));
  }
  if (plan.history_backfilled) {
    const pct = Math.round((plan.history_backfill_coverage || 0) * 100);
    bits.push(t('burndown.caption.backfilled', { tasks: plan.history_backfill_tasks, pct }));
  }
  if (plan.history_warning) bits.push(plan.history_warning);
  return bits.join(' · ');
}

export function renderBurndown() {
  const box = $('burndownCards');
  if (!box) return;
  for (const chart of charts.values()) chart.destroy();
  charts.clear();
  box.innerHTML = '';

  const today = state.data.generated_at.slice(0, 10);
  const rm = state.data.repo_meta || {};
  for (const [repo, meta] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const plan = meta.plan;
    // 兩個 key 都冇 = 舊 metrics.json,成張卡唔出。history_error 有 = 今次
    // 讀唔到,出張卡講明 —— 靜靜哋消失同畫一條平線一樣咁誤導。
    if (!plan || (!plan.history_error && !(plan.history || []).length)) continue;

    const series = burndownSeries(plan, today);
    const caption = plan.history_error || captionFor(series, plan);
    const card = document.createElement('div');
    card.className = 'burndown-card';
    const hasTrend = !plan.history_error && series.status !== 'single-point';
    const source = `<a href="${esc(planUrl(repo, plan))}" target="_blank" rel="noopener">${esc(plan.path)}</a>`;
    const sourceKind = plan.history_backfilled
      ? t('burndown.source.backfilledKind') : t('burndown.source.commitKind');
    const generated = (state.data.generated_at || '').slice(0, 10) || '—';
    const openCount = (plan.open_tasks || []).length;
    card.innerHTML = `<div class="burn-card-head">
        <div><div class="burn-eyebrow">PROJECT BURNDOWN</div>
          <div class="t">${esc(repo.split('/').pop())}</div></div>
        <div class="burn-source">${t('burndown.source.asOf', { date: esc(generated) })}<br>${t('burndown.source.prefix', { link: source, kind: esc(sourceKind) })}</div>
      </div>
      ${plan.history_error ? `<div class="burn-error">${esc(plan.history_error)}</div>` : summaryHTML(plan, series, today)}
      ${plan.history_error ? '' : `<div class="burn-chart-head"><strong>${esc(t('burndown.chart.headTitle'))}</strong><span>${esc(t('burndown.chart.headHint'))}</span></div>`}
      ${hasTrend
        ? `<div class="chart-box"><canvas aria-label="${esc(t('burndown.chart.ariaLabel', { repo: repo.split('/').pop() }))}"></canvas></div>`
        : plan.history_error ? '' : `<div class="burn-chart-empty"><strong>${esc(t('burndown.chart.emptyTitle'))}</strong><span>${esc(t('burndown.chart.emptyHint'))}</span></div>`}
      ${plan.history_error ? '' : `<details class="burn-task-details"><summary>${esc(t('burndown.details.summary', { n: openCount }))}</summary>${timelineHTML(plan, today)}</details>`}
      ${caption ? `<div class="note">${esc(caption)}</div>` : ''}`;
    box.appendChild(card);

    if (plan.history_error || !hasTrend) continue; // 冇趨勢就唔畫一條扮有方向嘅平線
    if (typeof Chart === 'undefined') continue;  // CDN 未 load 到,唔好阻住其他區塊
    charts.set(repo, new Chart(card.querySelector('canvas'), {
      type: 'line',
      plugins: [todayMarker],
      data: {
        labels: series.days.map((d) => d.slice(5)),
        datasets: [
          { label: t('burndown.chart.datasetRemaining'), data: series.remaining, borderColor: '#1F3A5F',
            backgroundColor: '#1F3A5F',
            pointRadius: (ctx) => ctx.dataIndex === series.todayIndex ? 4 : 0,
            pointHoverRadius: 5, borderWidth: 2.5, stepped: 'before', tension: 0,
            spanGaps: false },
          { label: t('burndown.chart.datasetScope'), data: series.scope, borderColor: '#8FA8CB',
            pointRadius: 0, borderWidth: 1.5, borderDash: [2, 2],
            stepped: 'before', tension: 0 },
          { label: t('burndown.chart.datasetIdeal'), data: series.ideal, borderColor: '#9AA5A0',
            pointRadius: 0, borderWidth: 1.5, borderDash: [6, 4], tension: 0 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', align: 'end',
                    labels: { boxWidth: 18, boxHeight: 2, padding: 16, usePointStyle: false } },
          tooltip: {
            callbacks: {
              title: (items) => items.length ? series.days[items[0].dataIndex] : '',
              label: (ctx) => ctx.raw == null ? '' : t('burndown.chart.tooltipLabel', { label: ctx.dataset.label, value: ctx.raw }),
            },
          },
          todayMarker: { index: series.todayIndex },
        },
        scales: {
          x: { grid: { display: false },
               ticks: { autoSkip: true, maxTicksLimit: 8, maxRotation: 0 } },
          y: { beginAtZero: true, ticks: { precision: 0 },
               grid: { color: '#ECEEE7' },
               title: { display: true, text: t('burndown.chart.yAxisTitle') } },
        },
      },
    }));
  }
}
