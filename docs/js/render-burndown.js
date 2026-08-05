import { state, $, esc, repoInScope } from './data.js';
import { burndownSeries } from './burndown.js?v=zh-20260805-5';
import { timelineHTML } from './render-timeline.js?v=zh-20260805-3';
import { timelineStrip } from './timeline.js';
import { completionForecast, scopeChange } from './management.js?v=zh-20260805-5';

/** 每個 repo 一個 Chart 實例。state.chart 得一個位,係每週圖嘅;
 *  唔另開一本帳,重畫嗰陣舊 canvas 會漏返出嚟。 */
const charts = new Map();

const CAPTION = {
  'single-point': '只有一個觀測點,未成趨勢',
};

/** 冇理想線嘅三個原因,逐個有自己嘅講法 —— 讀嘅人要知去改 plan.md 邊度。 */
const IDEAL_CAPTION = {
  'no-due': 'plan.md 冇 due: — 冇理想線',
  'due-unusable': 'plan.md 個 due: 唔係一個有效日期 — 冇理想線',
  'due-not-after-start': 'due: 唔遲過起點,拉唔出理想線',
};

/** 條軸個起點由邊層話事。每次都出:同一條軸,由 repo 開檔拉起同由第一次
 *  改 plan.md 拉起,理想線同 SPI 嘅意思完全唔同,但畫面上一模一樣。 */
const START_CAPTION = {
  plan: '起點:plan.md start:',
  repo: '起點:repo 第一個 commit',
  observation: '起點:第一次改 plan.md',
};

/** 宣告咗但用唔到嘅 start: —— 兩個原因要改嘅嘢唔同。冇宣告唔係一個錯,
 *  所以呢度冇第三個 key。 */
const START_REASON_CAPTION = {
  'start-unusable': 'plan.md 個 start: 唔係一個畫得出嘅日期',
  'start-after-history': 'start: 遲過第一個觀測,冇採用',
};

const FORECAST_REASON = {
  'no-plan': '未有計劃範圍',
  'not-enough-history': '需要最少 2 個觀測點',
  'history-too-short': '需要最少 7 日歷史',
  'no-observed-progress': '未觀測到完成速度',
};

const STATUS_LABEL = {
  complete: '已完成',
  'on-track': '按計劃',
  'at-risk': '有風險',
  'off-track': '落後計劃',
  unknown: '趨勢未明',
};

const shortDate = (date) => date ? date.slice(5).replace('-', '/') : '—';
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
    const reason = timeline.dueReason === 'due-unusable' ? 'plan.md 日期無效'
      : timeline.dueReason === 'due-not-after-start' ? '目標日唔遲過起點'
        : 'plan.md 未設定';
    return metricHTML('目標日', '—', reason, 'is-unknown');
  }
  const detail = timeline.daysLeft == null ? '未能計算剩餘日數'
    : timeline.daysLeft >= 0 ? `剩 ${timeline.daysLeft} 日`
      : `逾期 ${Math.abs(timeline.daysLeft)} 日`;
  return metricHTML('目標日', shortDate(timeline.due), detail,
    timeline.daysLeft != null && timeline.daysLeft < 0 ? 'is-bad' : '');
}

function scopeMetric(summary) {
  const { scope } = summary;
  if (!scope.available) return metricHTML('範圍變動', '—', '未有歷史基線', 'is-unknown');
  const tone = scope.net > 0 ? 'is-warn' : scope.net < 0 ? 'is-good' : '';
  const prefix = summary.backfilled && scope.baselineDate
    ? `由 ${shortDate(scope.baselineDate)} 起` : '起點';
  return metricHTML('範圍變動', signed(scope.net),
    `${prefix} ${scope.baseline} → 現在 ${scope.current}`, tone);
}

function forecastMetric(summary) {
  const { forecast, timeline } = summary;
  if (forecast.status === 'complete') return metricHTML('預測完成', '已完成', '實際結果', 'is-good');
  if (forecast.status !== 'forecast') {
    return metricHTML('預測完成', '—', FORECAST_REASON[forecast.reason] || '暫時不可用', 'is-unknown');
  }
  let detail = `${forecast.ratePerWeek} 項／週 · ${forecast.confidence === 'high' ? '高' : forecast.confidence === 'medium' ? '中' : '低'}信心`;
  if (timeline.due) {
    const delta = Math.round((Date.parse(`${forecast.projected}T00:00:00Z`)
      - Date.parse(`${timeline.due}T00:00:00Z`)) / 864e5);
    detail += delta > 0 ? ` · 遲 ${delta} 日` : delta < 0 ? ` · 早 ${Math.abs(delta)} 日` : ' · 準時';
  }
  return metricHTML('預測完成', shortDate(forecast.projected), detail,
    forecast.late ? 'is-bad' : 'is-good');
}

function headlineHTML(summary) {
  const bits = [];
  if (summary.status === 'complete') {
    bits.push('計劃範圍已全部完成');
  } else if (summary.gapPct != null) {
    const abs = Math.abs(Math.round(summary.gapPct));
    bits.push(summary.gapPct < 0
      ? `實際進度比今日計劃落後 ${abs} 個百分點`
      : summary.gapPct > 0
        ? `實際進度比今日計劃領先 ${abs} 個百分點`
        : '實際進度貼合理想線');
  } else {
    bits.push('現有資料未足以判斷進度差距');
  }
  if (summary.remainingGap != null && summary.remainingGap > 0) {
    bits.push(`比理想線多 ${Math.ceil(summary.remainingGap)} 項未完成`);
  }
  if (summary.timeline.overdue > 0) bits.push(`${summary.timeline.overdue} 項工作已過期`);
  return `<div class="burn-callout">
    <span class="burn-status is-${summary.status}">${esc(STATUS_LABEL[summary.status])}</span>
    <strong>${esc(bits.join(' · '))}</strong>
  </div>`;
}

function summaryHTML(plan, series, today) {
  const summary = managementSummary(plan, series, today);
  const progressValue = summary.progressPct == null ? '—' : `${Math.round(summary.progressPct)}%`;
  const progressTone = summary.status === 'off-track' ? 'is-bad'
    : summary.status === 'at-risk' ? 'is-warn'
      : summary.status === 'complete' || summary.status === 'on-track' ? 'is-good' : 'is-unknown';
  return headlineHTML(summary)
    + '<div class="burn-metrics">'
    + metricHTML('完成進度', progressValue, `${summary.done} / ${summary.total} 已完成`, progressTone)
    + metricHTML('剩餘工作', String(summary.remaining), '項未完成')
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
    ctx.fillText('今日', x, top - 3);
    ctx.restore();
  },
};

function captionFor(series, plan) {
  const bits = [];
  if (CAPTION[series.status]) bits.push(CAPTION[series.status]);
  if (START_CAPTION[series.startSource]) bits.push(START_CAPTION[series.startSource]);
  if (START_REASON_CAPTION[series.startReason]) {
    bits.push(START_REASON_CAPTION[series.startReason]);
  }
  // 以前呢度睇 `!series.due`,即係「有冇死線」。但一個宣告咗、畫唔出嘅
  // 死線(早過或者啱啱等於第一個觀測)一樣係 `due` 有值 —— 結果係冇線
  // 又冇解釋,正正係 spec §7 唔准嘅嘢。改為問 burndownSeries 本人點解冇
  // 線:條線畫唔畫同呢句講唔講,由同一個 idealReason 話事。
  if (series.idealReason) {
    bits.push(IDEAL_CAPTION[series.idealReason] || '冇理想線');
  }
  // 呢句淨係喺起點真係由「現存最早嗰個觀測」話事嗰陣先啱。起點由 start:
  // 或者 repo 開檔話事嘅時候,截斷咗嘅係中間嗰段觀測,唔係條理想線個錨 ——
  // 照出就係講錯嘢。
  if (series.truncated && series.startSource === 'observation') {
    bits.push('歷史已截斷,理想線由現存最早嗰個觀測起計');
  }
  if (plan.history_backfilled) {
    const pct = Math.round((plan.history_backfill_coverage || 0) * 100);
    bits.push(`完成趨勢由 ${plan.history_backfill_tasks} 項 task done: 日期回填（覆蓋 ${pct}%）；scope 變動只計真實 plan snapshot`);
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
    const sourceKind = plan.history_backfilled ? 'task done: 日期 + commit 歷史' : 'commit 歷史';
    const generated = (state.data.generated_at || '').slice(0, 10) || '—';
    const openCount = (plan.open_tasks || []).length;
    card.innerHTML = `<div class="burn-card-head">
        <div><div class="burn-eyebrow">PROJECT BURNDOWN</div>
          <div class="t">${esc(repo.split('/').pop())}</div></div>
        <div class="burn-source">數據截至 ${esc(generated)} · 每日 05:00 HKT 更新<br>來源：${source} ${sourceKind}</div>
      </div>
      ${plan.history_error ? `<div class="burn-error">${esc(plan.history_error)}</div>` : summaryHTML(plan, series, today)}
      ${plan.history_error ? '' : `<div class="burn-chart-head"><strong>剩餘工作趨勢</strong><span>數字愈接近 0 愈好</span></div>`}
      ${hasTrend
        ? `<div class="chart-box"><canvas aria-label="${esc(repo.split('/').pop())} 剩餘工作燃盡圖"></canvas></div>`
        : plan.history_error ? '' : `<div class="burn-chart-empty"><strong>未有足夠觀測畫趨勢</strong><span>目前只有 1 個 plan.md 歷史點；上面嘅進度同期限仍然可用。</span></div>`}
      ${plan.history_error ? '' : `<details class="burn-task-details"><summary>查看 ${openCount} 項未完成工作的期限</summary>${timelineHTML(plan, today)}</details>`}
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
          { label: '剩餘', data: series.remaining, borderColor: '#1F3A5F',
            backgroundColor: '#1F3A5F',
            pointRadius: (ctx) => ctx.dataIndex === series.todayIndex ? 4 : 0,
            pointHoverRadius: 5, borderWidth: 2.5, stepped: 'before', tension: 0,
            spanGaps: false },
          { label: '範圍上限', data: series.scope, borderColor: '#8FA8CB',
            pointRadius: 0, borderWidth: 1.5, borderDash: [2, 2],
            stepped: 'before', tension: 0 },
          { label: '理想剩餘', data: series.ideal, borderColor: '#9AA5A0',
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
              label: (ctx) => ctx.raw == null ? '' : `${ctx.dataset.label}：${ctx.raw} 項`,
            },
          },
          todayMarker: { index: series.todayIndex },
        },
        scales: {
          x: { grid: { display: false },
               ticks: { autoSkip: true, maxTicksLimit: 8, maxRotation: 0 } },
          y: { beginAtZero: true, ticks: { precision: 0 },
               grid: { color: '#ECEEE7' },
               title: { display: true, text: '工作數' } },
        },
      },
    }));
  }
}
