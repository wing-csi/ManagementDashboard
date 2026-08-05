/** Plan 日期嘅共用規矩 —— burndown 同 timeline 兩張圖都要一模一樣嘅答案。
 *
 *  呢啲嘢本來係 burndown.js 嘅私有嘢,用咗三個修正 commit 先至啱
 *  (04b57d2 日曆驗證、514608b 冇線要講點解、9be6968 commit list 分頁)。
 *  兩份各自演化嘅日期驗證,遲早會喺同一個 metrics.json 上面畫出兩個唔同
 *  嘅結論,而兩個都會睇落好合理。
 */

export const DAY = 864e5;

/** 一條軸最多畫幾多日(約十年)。
 *
 *  `plan.md` 係喺目標 repo 度人手改嘅,collector 由今次起會驗日曆,但舊
 *  `metrics.json` 入面嘅 `due_max` 未驗過。一個打錯咗嘅年份(`due:2926-09-18`)
 *  會叫 dayRange() 生 328,767 個日期,再乘三條 dataset 交去 Chart.js ——
 *  main thread 一卡就唔止呢張卡死,成個 dashboard 一齊死。 */
export const MAX_DAYS = 3653;

export const toMs = (s) => new Date(s + 'T00:00:00Z').getTime();
export const toISO = (ms) => new Date(ms).toISOString().slice(0, 10);

/** start..end(包頭包尾)有幾多日;任何一邊唔係真日期就出 NaN。 */
export const spanDays = (start, end) => Math.floor((toMs(end) - toMs(start)) / DAY) + 1;

/** 真係存在嘅日曆日?
 *
 *  唔淨止係 NaN check:`2026-13-01` 同 `2026-08-32` 出 NaN,但 `2026-02-30`
 *  唔會 —— JS 會靜靜哋當佢係 3 月 2 日。咁樣喺條軸上面就永遠 indexOf 唔到,
 *  變成一個「冇線,而且講錯咗理由」嘅 card。Round-trip 返轉頭一定要係
 *  原本嗰串字,兩種都一次過擋晒。 */
export const realDate = (s) => {
  const ms = toMs(s);
  return Number.isFinite(ms) && toISO(ms) === s;
};

/** start..end(包頭包尾)每一日嘅 ISO 日期。
 *
 *  封頂 MAX_DAYS 個係最後一道 allocation 閘(例如一個 clock 壞咗嘅 commit
 *  日期);正常範圍同呢個上限差幾個數量級,撞唔到。 */
export function dayRange(start, end) {
  const out = [];
  for (let ms = toMs(start); ms <= toMs(end) && out.length < MAX_DAYS; ms += DAY) {
    out.push(toISO(ms));
  }
  return out;
}

/** 一份 plan 嘅計劃窗口:`{start, due, dueReason}`。
 *
 *  `dueReason` 唔係 null 就代表冇一個用得嘅終點,而個值就係要同用家講嘅
 *  原因。四個原因要分得開,因為要改嘅嘢完全唔同:冇 history(舊數據)、
 *  plan.md 冇寫 due:、寫咗但唔係一個畫得出嘅日期、寫咗但唔遲過起點。
 *
 *  注意 `due` 喺 'due-not-after-start' 嗰陣**仍然唔係 null** —— 佢係一個
 *  真日期,畫得落條軸,只不過拉唔出一條線。條軸要用返佢。 */
export function resolvePlanWindow(plan) {
  const history = (plan || {}).history;
  if (!Array.isArray(history) || history.length === 0) {
    return { start: null, due: null, dueReason: 'no-history' };
  }
  const start = history[0].date;
  // `due_max` 淨係「shape 啱」就入到嚟(舊 metrics.json 更加乜都冇驗過),
  // 而佢係一個字串 max() 揀出嚟嘅 —— `2026-13-01` 呢類打錯嘅日期會贏晒
  // 同年所有真日期。攞唔到 timestamp(NaN)或者離譜到要畫十年以上,兩種
  // 都當「畫唔出」,唔好帶落條軸度。
  const declared = plan.due_max || null;
  const usable = !!declared && realDate(declared)
    && spanDays(start, declared) <= MAX_DAYS;
  const due = usable ? declared : null;
  // 太早嘅 due 唔算「畫唔出」:佢畫得出,只係拉唔到線 —— 所以佢喺 due
  // 有值嘅前提下先至判,同上面兩個原因分開。
  const dueReason = !declared ? 'no-due'
    : !usable ? 'due-unusable'
      : due <= start ? 'due-not-after-start'
        : null;
  return { start, due, dueReason };
}
