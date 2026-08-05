import { state, $, esc, repoInScope } from './data.js';
import { burndownSeries } from './burndown.js';
import { timelineHTML } from './render-timeline.js?v=zh-20260805-3';

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
    ctx.restore();
  },
};

function captionFor(series) {
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
    const caption = plan.history_error || captionFor(series);
    const card = document.createElement('div');
    card.className = 'burndown-card';
    card.innerHTML = `<div class="t">${esc(repo.split('/').pop())}
        <span style="color:var(--muted)">· 燃盡圖（${esc(plan.path)}）</span></div>
      ${plan.history_error ? '' : '<div class="chart-box"><canvas></canvas></div>'}
      ${plan.history_error ? '' : timelineHTML(plan, today)}
      ${caption ? `<div class="note" style="color:var(--muted)">${esc(caption)}</div>` : ''}`;
    box.appendChild(card);

    if (plan.history_error) continue;            // 冇數據,冇圖,但有交代
    if (typeof Chart === 'undefined') continue;  // CDN 未 load 到,唔好阻住其他區塊
    charts.set(repo, new Chart(card.querySelector('canvas'), {
      type: 'line',
      plugins: [todayMarker],
      data: {
        labels: series.days.map((d) => d.slice(5)),
        datasets: [
          { label: '剩餘', data: series.remaining, borderColor: '#1F3A5F',
            pointRadius: 0, borderWidth: 2, tension: 0, spanGaps: false },
          { label: '總範圍', data: series.scope, borderColor: '#8FA8CB',
            pointRadius: 0, borderWidth: 1.5, borderDash: [2, 2], tension: 0 },
          { label: '理想', data: series.ideal, borderColor: '#9AA5A0',
            pointRadius: 0, borderWidth: 1.5, borderDash: [6, 4], tension: 0 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom',
                    labels: { boxWidth: 10, boxHeight: 10, padding: 12 } },
          todayMarker: { index: series.todayIndex },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 },
               title: { display: true, text: '剩餘工作數' } },
        },
      },
    }));
  }
}
