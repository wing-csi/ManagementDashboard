/** Plan timeline 條嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  Marker 來自 `plan.open_tasks[]`,即係**未打勾**嗰啲。做完嘅 task 唔會
 *  留低痕跡,所以呢條線讀做「仲有乜嘢喺前面」,唔係「成個項目嘅里程碑」。
 *  卡上要寫明呢點:task 一路做完條線一路變疏,同「一切順利」喺畫面上
 *  睇落一模一樣。
 */

import {
  DAY, MAX_DAYS, toMs, toISO, spanDays, realDate, resolvePlanWindow,
} from './plan-dates.js';

/** 急切度淨係睇日期 —— 同「項目」分頁 milestone 行嘅 late 邏輯一致。 */
function urgencyOf(daysFromToday) {
  if (daysFromToday < 0) return 'overdue';
  if (daysFromToday <= 7) return 'soon7';
  if (daysFromToday <= 14) return 'soon14';
  return 'later';
}

const EMPTY = {
  status: 'no-history', start: null, due: null, dueReason: 'no-history',
  startSource: null, startReason: null,
  axisStart: null, axisEnd: null, barLeftPct: 0, barWidthPct: 0,
  todayPct: null, markers: [], spi: null, spiReason: 'no-history',
  daysLeft: null, overdue: 0, invalidDues: 0, allDone: false,
};

export function timelineStrip(plan, todayStr) {
  const { start, startSource, startReason, due, dueReason } = resolvePlanWindow(plan);
  if (!start) return { ...EMPTY };

  const open = (plan.open_tasks || []).filter((t) => t && t.due);
  const valid = open.filter((t) => realDate(t.due));
  const invalidDues = open.length - valid.length;

  // 條軸要罩得住每一粒真 marker 同今日。一粒跌咗出畫面,就係「冇畫又冇
  // 講」;今日跌咗出去,「過唔過期」就冇咗參照點。
  const dates = valid.map((t) => t.due);
  const axisStart = [start, ...dates].sort()[0];
  let axisEnd = [due || start, ...dates, todayStr].sort().pop();
  // 同 dayRange 一樣嘅 allocation 閘:一個壞日期唔可以令個 axis 拉到十年外。
  if (spanDays(axisStart, axisEnd) > MAX_DAYS) {
    axisEnd = toISO(toMs(axisStart) + (MAX_DAYS - 1) * DAY);
  }

  const span = spanDays(axisStart, axisEnd);
  const pct = (d) => (span <= 1 ? 0 : ((toMs(d) - toMs(axisStart)) / DAY) / (span - 1) * 100);

  const todayMs = toMs(todayStr);
  const byDate = new Map();
  for (const t of valid) {
    if (!byDate.has(t.due)) byDate.set(t.due, []);
    byDate.get(t.due).push({
      title: t.title || '', priority: t.priority || null, bug: !!t.bug,
    });
  }
  const markers = [...byDate.keys()].sort().map((date) => {
    const tasks = byDate.get(date);
    const daysFromToday = Math.round((toMs(date) - todayMs) / DAY);
    return {
      date, leftPct: pct(date), urgency: urgencyOf(daysFromToday),
      daysFromToday, count: tasks.length, tasks,
    };
  });
  const overdue = markers
    .filter((mk) => mk.urgency === 'overdue')
    .reduce((n, mk) => n + mk.count, 0);

  // 條 bar 係「計劃咗幾耐」。冇一個用得嘅終點就冇計劃窗口 —— 改為畫到
  // 今日,讀做「行咗幾耐」。兩者喺畫面上一樣咁闊,所以 caption 一定要
  // 講返係邊一種(render-timeline.js)。
  const barEnd = dueReason ? todayStr : due;
  const barLeftPct = pct(start);
  const barWidthPct = Math.max(0, pct(barEnd) - barLeftPct);

  const total = plan.total || 0;
  const done = plan.done || 0;
  let spi = null;
  let spiReason = null;
  if (dueReason) {
    spiReason = dueReason;
  } else if (total <= 0) {
    // 0/0 係 NaN,而 NaN 輸晒所有 band 比較,最後靜靜哋顯示做「嚴重落後」。
    spiReason = 'no-tasks';
  } else {
    const elapsed = (todayMs - toMs(start)) / (toMs(due) - toMs(start));
    if (!(elapsed > 0)) spiReason = 'not-started';
    else spi = +((done / total) / elapsed).toFixed(2);
  }

  return {
    status: 'ok', start, startSource, startReason, due, dueReason,
    axisStart, axisEnd,
    barLeftPct, barWidthPct,
    todayPct: todayStr < axisStart ? null : pct(todayStr),
    markers, spi, spiReason,
    // 冇終點就冇「剩幾多」—— 唔可以攞今日或者最遲嗰粒 marker 嚟頂替。
    daysLeft: dueReason ? null : Math.round((toMs(due) - todayMs) / DAY),
    overdue, invalidDues,
    allDone: total > 0 && done >= total,
  };
}
