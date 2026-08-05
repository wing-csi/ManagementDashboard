/** 數據新鮮度 —— 純計算,冇 DOM,所以可以獨立測。
 *
 *  「而家」係一個參數,唔係喺入面 call Date.now()。呢點唔係風格問題:模組自己
 *  攞當前時間嘅話,測試就冇得釘住「而家」,而所有用固定 fixture 嘅 test 會隨住
 *  月曆行前慢慢變紅(metrics-fixture-burndown.json 釘咗 2026-08-04)。同
 *  burndownSeries(plan, todayStr) 同 timelineStrip(plan, todayStr) 收 today
 *  做參數,係同一個做法。
 *
 *  呢度**只係出提示,唔掂任何計算**。過期嗰陣,refDate() 同條今日線一律照用
 *  generated_at 做今日,即係照舊唔準 —— 個 banner 講嘅係「唔好信呢頁幾新」,
 *  唔係幫你修正啲數(spec §7)。
 */

const HOUR = 3600e3;
const DAY = 864e5;

/** 過期線:48 個鐘。
 *
 *  唔係 24 —— pipeline 每日 05:00 HKT(21:00 UTC)行,所以一日入面大部分時間,
 *  最新可能嘅數據本身已經 20 幾個鐘大。一條「超過 24 鐘」嘅規矩會每日下晝都嘈
 *  一次,而嘈得滯嘅提示等於冇提示。48 鐘代表至少一次 run 真係冇出到嘢。 */
export const STALE_MS = 48 * HOUR;

/** 時間戳喺未來幾多先當個 clock 唔啱。平時嘅 skew 食得起,唔好為佢彈警告。 */
export const FUTURE_TOLERANCE_MS = HOUR;

/** `{status, ageDays}`。
 *
 *  四個 status 要分得開,因為每個要講嘅嘢同要改嘅嘢都唔同:冇時間戳唔等於數據
 *  舊,而未來嘅時間戳代表 browser clock 或者 collector 有問題。併埋一齊就係
 *  講緊一件假嘢。
 *
 *  `ageDays` 淨係喺 'stale' 嗰陣有數 —— 另外三種都冇一個講得出口嘅「幾多日前」。 */
export function staleness(generatedAt, nowMs) {
  const ms = typeof generatedAt === 'string' ? Date.parse(generatedAt) : NaN;
  if (!Number.isFinite(ms)) return { status: 'unreadable', ageDays: null };

  const age = nowMs - ms;
  if (age < -FUTURE_TOLERANCE_MS) return { status: 'future', ageDays: null };
  // 門檻用毫秒判,唔用日數判:啱啱 48 鐘係 fresh,但佢已經係「2 日」。用日數
  // 判嘅話 49 鐘同 71 鐘都係 2,一個應該出一個唔應該出,就分唔開。
  if (age > STALE_MS) return { status: 'stale', ageDays: Math.floor(age / DAY) };
  return { status: 'fresh', ageDays: null };
}

/** 每個 status 有自己嘅講法 —— 跟返 timeline spec §8「每一個缺席都要自己解釋」。
 *  三句都要講得出「去邊度查」,淨係話「有問題」等於冇講。 */
const MESSAGE = {
  stale: (s) => `數據係 ${s.ageDays} 日前嘅 —— nightly pipeline 可能停咗。`
    + '去 GitHub Actions 睇下最近嘅 collect run 紅咗未。',
  unreadable: () => '讀唔到數據嘅時間戳,所以唔知呢頁係幾時嘅數。'
    + '查 metrics.json 個 generated_at。',
  future: () => '數據嘅時間戳喺未來 —— 部機或者 collector 個時間唔啱。'
    + '呢頁所有「今日」、「過期」、SPI 都信唔過。',
};

export function stalenessMessage(s) {
  const build = MESSAGE[s.status];
  return build ? build(s) : '';
}
