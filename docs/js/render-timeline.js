import { esc } from './data.js';
import { timelineStrip } from './timeline.js';
import { t } from './i18n/index.js?v=i18n-20260922-1';

/** SPI 三個 band。同 burndown 一樣,顏色由 CSS class 話事,唔喺 JS 度寫死。 */
function spiBand(spi) {
  if (spi >= 1) return { cls: 'tl-ok', key: 'band.onTrack' };
  if (spi >= 0.8) return { cls: 'tl-warn', key: 'band.behind' };
  return { cls: 'tl-bad', key: 'band.seriouslyBehind' };
}

/** 冇 SPI 嘅五個原因,逐個有自己嘅講法 —— 頭三個同 burndown 個
 *  IDEAL_CAPTION 用同一套字,因為背後係同一個 dueReason。 */
const NO_SPI_KEY = {
  'no-due': 'noSpi.noDue',
  'due-unusable': 'noSpi.dueUnusable',
  'due-not-after-start': 'noSpi.dueNotAfterStart',
  'not-started': 'noSpi.notStarted',
  'no-tasks': 'noSpi.noTasks',
};

function headHTML(s) {
  const bits = [];
  if (s.spi != null) {
    const band = spiBand(s.spi);
    bits.push(`<span class="${band.cls}">${esc(t('timeline.spiLabel', { spi: s.spi, band: t(`timeline.${band.key}`) }))}</span>`);
  } else {
    const reasonKey = NO_SPI_KEY[s.spiReason];
    bits.push(`<span class="tl-muted">${esc(reasonKey ? t(`timeline.${reasonKey}`) : t('timeline.noSpi.default'))}</span>`);
  }
  if (s.daysLeft != null) {
    bits.push(s.daysLeft >= 0
      ? t('timeline.daysLeft', { n: s.daysLeft })
      : `<span class="tl-bad">${esc(t('timeline.daysLate', { n: Math.abs(s.daysLeft) }))}</span>`);
  }
  if (s.overdue > 0) {
    bits.push(`<span class="tl-bad">${esc(t('timeline.overdueCount', { n: s.overdue }))}</span>`);
  }
  return `<div class="tl-head">${bits.join(' · ')}</div>`;
}

function markerHTML(mk) {
  const lines = mk.tasks.map((task) => {
    const tags = [task.priority, task.bug ? '#bug' : null].filter(Boolean).join(' ');
    return tags ? `${task.title} (${tags})` : task.title;
  });
  const tip = `${mk.date}\n${lines.join('\n')}`;
  const label = mk.count > 1 ? String(mk.count) : '';
  return `<span class="tl-mark tl-${mk.urgency}" style="left:${mk.leftPct.toFixed(2)}%"`
    + ` title="${esc(tip)}">${esc(label)}</span>`;
}

/** 條線一定要講嘅嘢。第一句每次都出:條線只畫未打勾嘅 task,唔講嘅話
 *  「做完嘢令條線變疏」同「一切順利」喺畫面上分唔開。 */
function noteHTML(s) {
  const bits = [t('timeline.note.onlyUnfinished')];
  if (s.allDone) bits.push(t('timeline.note.allDone'));
  else if (!s.markers.length) bits.push(t('timeline.note.noDues'));
  if (s.dueReason === 'no-due') bits.push(t('timeline.note.noDue'));
  if (s.dueReason === 'due-unusable') bits.push(t('timeline.note.dueUnusable'));
  if (s.dueReason === 'due-not-after-start') bits.push(t('timeline.note.dueNotAfterStart'));
  if (s.invalidDues > 0) bits.push(t('timeline.note.invalidDues', { n: s.invalidDues }));
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
