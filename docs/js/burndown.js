/** 項目 burndown 嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  收集端只出「plan.md 真係改過嗰啲日」嘅觀測(見 scripts/plan_history.py)。
 *  中間嗰啲平坦日子喺呢度 carry-forward 補返:焗入 JSON 嘅話,一條階梯函數
 *  同真正嘅每日取樣就完全分唔開。
 */

const DAY = 864e5;
const toMs = (s) => new Date(s + 'T00:00:00Z').getTime();
const toISO = (ms) => new Date(ms).toISOString().slice(0, 10);

/** start..end(包頭包尾)每一日嘅 ISO 日期。 */
function dayRange(start, end) {
  const out = [];
  for (let ms = toMs(start); ms <= toMs(end); ms += DAY) out.push(toISO(ms));
  return out;
}

export function burndownSeries(plan, todayStr) {
  const history = (plan || {}).history;
  if (!Array.isArray(history) || history.length === 0) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, truncated: false };
  }

  const start = history[0].date;
  const due = plan.due_max || null;
  // 死線過咗都要見到今日,否則個圖會喺死線度斷;ISO 日期直接字串比大細。
  const lastObs = history[history.length - 1].date;
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
  const startTotal = history[0].total;
  const ideal = days.map((_, i) => {
    if (dueIndex <= 0 || i > dueIndex) return null;
    return +(startTotal * (1 - i / dueIndex)).toFixed(2);
  });

  return {
    status: history.length === 1 ? 'single-point' : 'ok',
    days, remaining, scope, ideal, todayIndex, due,
    truncated: !!plan.history_truncated,
  };
}
