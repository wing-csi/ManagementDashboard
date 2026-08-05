/** Snapshot freshness is pure calculation so callers can supply a fixed clock. */
const HOUR = 3600e3;
const DAY = 864e5;

/** More than 48 hours means at least one nightly collection was missed. */
export const STALE_MS = 48 * HOUR;

/** Tolerate ordinary browser/collector clock skew before warning. */
export const FUTURE_TOLERANCE_MS = HOUR;

/** Return one freshness state without changing any dashboard calculations. */
export function staleness(generatedAt, nowMs) {
  const generatedMs = typeof generatedAt === 'string' ? Date.parse(generatedAt) : NaN;
  if (!Number.isFinite(generatedMs) || !Number.isFinite(nowMs)) {
    return { status: 'unreadable', ageDays: null };
  }

  const ageMs = nowMs - generatedMs;
  if (ageMs < -FUTURE_TOLERANCE_MS) {
    return { status: 'future', ageDays: null };
  }
  if (ageMs > STALE_MS) {
    return { status: 'stale', ageDays: Math.floor(ageMs / DAY) };
  }
  return { status: 'fresh', ageDays: null };
}

const MESSAGE = {
  stale: (result) => `數據係 ${result.ageDays} 日前嘅舊快照；所有「今日」、逾期同預測都以舊數據為準。`
    + '請到 GitHub Actions 檢查最近的收集及部署工作流程。',
  unreadable: () => '讀唔到數據嘅時間戳，所以唔知呢頁係幾時嘅數。請檢查 metrics.json 的 generated_at 欄位。',
  future: () => '數據嘅時間戳喺未來，本機或數據收集器的時間唔啱。呢頁所有「今日」、過期同 SPI 都信唔過。',
};

export function stalenessMessage(result) {
  const build = MESSAGE[result.status];
  return build ? build(result) : '';
}
