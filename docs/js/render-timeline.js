import { esc } from './data.js';
import { timelineStrip } from './timeline.js';

/** SPI 三個 band。同 burndown 一樣,顏色由 CSS class 話事,唔喺 JS 度寫死。 */
function spiBand(spi) {
  if (spi >= 1) return { cls: 'tl-ok', text: '追得上' };
  if (spi >= 0.8) return { cls: 'tl-warn', text: '落後' };
  return { cls: 'tl-bad', text: '嚴重落後' };
}

/** 冇 SPI 嘅五個原因,逐個有自己嘅講法 —— 頭三個同 burndown 個
 *  IDEAL_CAPTION 用同一套字,因為背後係同一個 dueReason。 */
const NO_SPI = {
  'no-due': 'plan.md 冇 due: — 冇 SPI',
  'due-unusable': 'plan.md 個 due: 唔係一個有效日期 — 冇 SPI',
  'due-not-after-start': 'due: 唔遲過起點 — 冇 SPI',
  'not-started': '未開始',
  'no-tasks': 'plan.md 冇工作',
};

function headHTML(s) {
  const bits = [];
  if (s.spi != null) {
    const band = spiBand(s.spi);
    bits.push(`<span class="${band.cls}">SPI ${s.spi} · ${band.text}</span>`);
  } else {
    bits.push(`<span class="tl-muted">${esc(NO_SPI[s.spiReason] || '冇 SPI')}</span>`);
  }
  if (s.daysLeft != null) {
    bits.push(s.daysLeft >= 0
      ? `剩 ${s.daysLeft} 日`
      : `<span class="tl-bad">遲咗 ${Math.abs(s.daysLeft)} 日</span>`);
  }
  if (s.overdue > 0) bits.push(`<span class="tl-bad">${s.overdue} 項工作過咗期</span>`);
  return `<div class="tl-head">${bits.join(' · ')}</div>`;
}

function markerHTML(mk) {
  const lines = mk.tasks.map((t) => {
    const tags = [t.priority, t.bug ? '#bug' : null].filter(Boolean).join(' ');
    return tags ? `${t.title} (${tags})` : t.title;
  });
  const tip = `${mk.date}\n${lines.join('\n')}`;
  const label = mk.count > 1 ? String(mk.count) : '';
  return `<span class="tl-mark tl-${mk.urgency}" style="left:${mk.leftPct.toFixed(2)}%"`
    + ` title="${esc(tip)}">${esc(label)}</span>`;
}

/** 條線一定要講嘅嘢。第一句每次都出:條線只畫未打勾嘅 task,唔講嘅話
 *  「做完嘢令條線變疏」同「一切順利」喺畫面上分唔開。 */
function noteHTML(s) {
  const bits = ['條線只畫未做嘅工作'];
  if (s.allDone) bits.push('冇嘢剩低');
  else if (!s.markers.length) bits.push('plan.md 的工作冇寫 due:');
  if (s.dueReason === 'no-due') bits.push('冇目標日，時間條畫到今日為止');
  if (s.dueReason === 'due-unusable') bits.push('目標日唔係一個有效日期，時間條畫到今日為止');
  if (s.dueReason === 'due-not-after-start') bits.push('目標日唔遲過計劃起點，時間條畫到今日為止');
  if (s.invalidDues > 0) bits.push(`${s.invalidDues} 項工作的 due: 唔係有效日期，冇畫`);
  return `<div class="tl-note">${esc(bits.join(' · '))}</div>`;
}

export function timelineHTML(plan, todayStr) {
  const s = timelineStrip(plan, todayStr);
  if (s.status === 'no-history') return '';
  const today = s.todayPct == null ? ''
    : `<span class="tl-today" style="left:${s.todayPct.toFixed(2)}%"></span>`;
  return '<div class="tl">'
    + headHTML(s)
    + '<div class="tl-axis">'
    + `<span class="tl-bar" style="left:${s.barLeftPct.toFixed(2)}%;`
    + `width:${s.barWidthPct.toFixed(2)}%"></span>`
    + today
    + s.markers.map(markerHTML).join('')
    + '</div>'
    + `<div class="tl-scale"><span>${esc(s.axisStart)}</span>`
    + `<span>${esc(s.axisEnd)}</span></div>`
    + noteHTML(s)
    + '</div>';
}
