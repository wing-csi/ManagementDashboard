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

/** 一個 candidate 起點用唔用得。
 *
 *  三個條件缺一不可:係一個真日曆日、唔遲過第一個觀測(遲過就同 git 記錄
 *  矛盾,採用佢要切走真嘢)、而且唔遠到爆條軸 —— `dayRange()` 個 cap 係
 *  **剪尾**嘅,剪走今日同死線,比起唔採用衰好多。 */
const usableStart = (value, firstObs) =>
  !!value && realDate(value) && value <= firstObs
    && spanDays(value, firstObs) <= MAX_DAYS;

/** 一份 plan 嘅計劃窗口:`{start, startSource, startReason, due, dueReason}`。
 *
 *  起點行三層:`plan.md` 宣告嘅 `start:` → repo 第一個 commit → 第一個
 *  plan 觀測。頭兩層都係 optional 欄位,舊 `metrics.json` 兩個都冇,自然
 *  跌到第三層 —— 即係呢個 feature 之前嘅行為。
 *
 *  `startSource` 講用咗邊層,張卡要出返俾人睇:同一條軸,由 repo 開檔拉起
 *  同由第一次改 plan.md 拉起,理想線同 SPI 嘅意思完全唔同,但畫面上一模
 *  一樣。
 *
 *  `startReason` 淨係講「人手宣告咗但用唔到」。`repo_first_commit` 唔係人手
 *  寫嘅,攞唔到或者唔啱就靜靜跌落下一層 —— 出一句叫人去改乜嘢都冇。
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
    return { start: null, startSource: null, startReason: null,
             due: null, dueReason: 'no-history' };
  }
  const firstObs = history[0].date;
  const declaredStart = plan.start_min || null;
  const repoStart = plan.repo_first_commit || null;

  let start = firstObs;
  let startSource = 'observation';
  if (usableStart(declaredStart, firstObs)) {
    start = declaredStart;
    startSource = 'plan';
  } else if (usableStart(repoStart, firstObs)) {
    start = repoStart;
    startSource = 'repo';
  }
  // `realDate` 要行喺日期比大細之前:`'2026-13-01' > '2026-08-01'` 係字串
  // 比較,答「係」,但佢唔係遲咗 —— 佢根本唔係一個日期。揀錯咗個 reason,
  // 張卡就會叫人去改一個唔存在嘅問題。
  const startReason = (!declaredStart || startSource === 'plan') ? null
    : !realDate(declaredStart) ? 'start-unusable'
      : declaredStart > firstObs ? 'start-after-history'
        : 'start-unusable';

  // `due_max` 淨係「shape 啱」就入到嚟(舊 metrics.json 更加乜都冇驗過),
  // 而佢係一個字串 max() 揀出嚟嘅 —— `2026-13-01` 呢類打錯嘅日期會贏晒
  // 同年所有真日期。攞唔到 timestamp(NaN)或者離譜到要畫十年以上,兩種
  // 都當「畫唔出」,唔好帶落條軸度。個 span 由**解析咗嘅**起點度起計。
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
  return { start, startSource, startReason, due, dueReason };
}
