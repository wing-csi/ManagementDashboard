/** 項目 burndown 嘅數據整形 — 純計算,冇 DOM,所以可以獨立測。
 *
 *  收集端只出「plan.md 真係改過嗰啲日」嘅觀測(見 scripts/plan_history.py)。
 *  中間嗰啲平坦日子喺呢度 carry-forward 補返:焗入 JSON 嘅話,一條階梯函數
 *  同真正嘅每日取樣就完全分唔開。
 */

const DAY = 864e5;

/** 一條軸最多畫幾多日(約十年)。
 *
 *  `plan.md` 係喺目標 repo 度人手改嘅,collector 由今次起會驗日曆,但舊
 *  `metrics.json` 入面嘅 `due_max` 未驗過。一個打錯咗嘅年份(`due:2926-09-18`)
 *  會叫 dayRange() 生 328,767 個日期,再乘三條 dataset 交去 Chart.js ——
 *  main thread 一卡就唔止呢張卡死,成個 dashboard 一齊死。 */
const MAX_DAYS = 3653;

const toMs = (s) => new Date(s + 'T00:00:00Z').getTime();
const toISO = (ms) => new Date(ms).toISOString().slice(0, 10);

/** start..end(包頭包尾)有幾多日;任何一邊唔係真日期就出 NaN。 */
const spanDays = (start, end) => Math.floor((toMs(end) - toMs(start)) / DAY) + 1;

/** 真係存在嘅日曆日?
 *
 *  唔淨止係 NaN check:`2026-13-01` 同 `2026-08-32` 出 NaN,但 `2026-02-30`
 *  唔會 —— JS 會靜靜哋當佢係 3 月 2 日。咁樣喺條軸上面就永遠 indexOf 唔到,
 *  變成一個「冇線,而且講錯咗理由」嘅 card。Round-trip 返轉頭一定要係
 *  原本嗰串字,兩種都一次過擋晒。 */
const realDate = (s) => {
  const ms = toMs(s);
  return Number.isFinite(ms) && toISO(ms) === s;
};

/** start..end(包頭包尾)每一日嘅 ISO 日期。
 *
 *  封頂 MAX_DAYS 個係最後一道 allocation 閘(例如一個 clock 壞咗嘅 commit
 *  日期);正常範圍同呢個上限差幾個數量級,撞唔到。 */
function dayRange(start, end) {
  const out = [];
  for (let ms = toMs(start); ms <= toMs(end) && out.length < MAX_DAYS; ms += DAY) {
    out.push(toISO(ms));
  }
  return out;
}

export function burndownSeries(plan, todayStr) {
  const history = (plan || {}).history;
  if (!Array.isArray(history) || history.length === 0) {
    return { status: 'no-history', days: [], remaining: [], scope: [],
             ideal: [], todayIndex: -1, due: null, idealReason: 'no-history',
             truncated: false };
  }

  const start = history[0].date;
  const lastObs = history[history.length - 1].date;
  // `due_max` 淨係「shape 啱」就入到嚟(舊 metrics.json 更加乜都冇驗過),
  // 而佢係一個字串 max() 揀出嚟嘅 —— `2026-13-01` 呢類打錯嘅日期會贏晒
  // 同年所有真日期。攞唔到 timestamp(NaN)或者離譜到要畫十年以上,兩種
  // 都當「畫唔出」,唔好帶落條軸度。
  // 太早嘅 due 唔喺呢度擋:佢係一個畫得出嘅日期,只不過拉唔到條線 ——
  // 兩件事分開講,下面 dueIndex 嗰度處理。
  const declared = plan.due_max || null;
  const due = declared && realDate(declared)
    && spanDays(start, declared) <= MAX_DAYS ? declared : null;
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
  // 冇理想線就一定要講得出點解(spec §7),而三個原因要分得開:「plan.md
  // 冇寫 due:」、「寫咗但係唔係一個畫得出嘅日期」、同「寫咗,但佢唔遲過
  // 第一個觀測所以拉唔出一條線」——三種要改嘅嘢完全唔同。最後嗰種係設計
  // 內嘅正路 case:heading 級 due: 就算早過所有 task due 都照贏,所以一份
  // 死線之後先開檔嘅補救計劃,一開波就撞正。
  const idealReason = !declared ? 'no-due'
    : !due ? 'due-unusable'
      : dueIndex <= 0 ? 'due-not-after-start'
        : null;
  const startTotal = history[0].total;
  const ideal = days.map((_, i) => {
    // 同一個條件管住「畫唔畫」同「講唔講」,兩者就唔會各自飄走。
    if (idealReason || i > dueIndex) return null;
    return +(startTotal * (1 - i / dueIndex)).toFixed(2);
  });

  return {
    status: history.length === 1 ? 'single-point' : 'ok',
    days, remaining, scope, ideal, todayIndex, due, idealReason,
    truncated: !!plan.history_truncated,
  };
}
