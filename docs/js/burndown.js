/** 項目 burndown 嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  收集端只出「plan.md 真係改過嗰啲日」嘅觀測(見 scripts/plan_history.py)。
 *  中間嗰啲平坦日子喺呢度 carry-forward 補返:焗入 JSON 嘅話,一條階梯函數
 *  同真正嘅每日取樣就完全分唔開。
 *
 *  日期嗰套規矩(邊個 due_max 用得、點解用唔得)住喺 plan-dates.js,同
 *  timeline 條線共用 —— 兩張圖一定要對同一份 plan 講同一個答案。
 */

import { dayRange, resolvePlanWindow } from './plan-dates.js';

export function burndownSeries(plan, todayStr) {
  const { start, startSource, startReason, due, dueReason } = resolvePlanWindow(plan);
  if (!start) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, idealReason: 'no-history',
             startSource: null, startReason: null, truncated: false };
  }

  const history = plan.history;
  const lastObs = history[history.length - 1].date;
  // 死線過咗都要見到今日,否則個圖會喺死線度斷;ISO 日期直接字串比大細。
  const end = [due || lastObs, lastObs, todayStr].sort().pop();
  const days = dayRange(start, end);

  const byDate = new Map(history.map((h) => [h.date, h]));
  const todayIndex = days.indexOf(todayStr);
  const remaining = [];
  const scope = [];
  let cur = null;
  days.forEach((d, i) => {
    if (byDate.has(d)) cur = byDate.get(d);
    const past = todayIndex < 0 || i <= todayIndex;
    remaining.push(past && cur ? cur.total - cur.done : null);
    scope.push(past && cur ? cur.total : null);
  });

  // 理想線錨喺起點嘅 scope,唔係今日嘅 —— scope 加咗幾多,就係兩條線嘅開叉。
  const dueIndex = due ? days.indexOf(due) : -1;
  // 冇理想線就一定要講得出點解(spec §7)。四個原因而家由 resolvePlanWindow
  // 判,burndown 同 timeline 共用同一套字 —— 兩張卡對住同一份 plan,唔會
  // 一張話「冇寫 due:」另一張話「寫錯咗」。
  const idealReason = dueReason;
  const startTotal = history[0].total;
  const ideal = days.map((_, i) => {
    // 同一個條件管住「畫唔畫」同「講唔講」,兩者就唔會各自飄走。
    if (idealReason || i > dueIndex) return null;
    return +(startTotal * (1 - i / dueIndex)).toFixed(2);
  });

  return {
    status: history.length === 1 ? 'single-point' : 'ok',
    days, remaining, scope, ideal, todayIndex, due, idealReason,
    // 條線本身唔使知起點由邊層嚟,但張卡要講得出 —— 渲染層冇第二個途徑
    // 攞到,所以呢度要 pass 過去。
    startSource, startReason,
    truncated: !!plan.history_truncated,
  };
}
