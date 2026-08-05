const HOUR = 3600e3;
const DAY = 24 * HOUR;

/** Decide whether a generated snapshot is safe to treat as current.
 *
 * `nowMs` is supplied by the caller so the rule stays deterministic in tests.
 * This is warning-only: the rest of the dashboard deliberately keeps using
 * generated_at as its reference date so one snapshot never mixes two clocks.
 */
export function staleness(generatedAt, nowMs) {
  const generatedMs = Date.parse(generatedAt || '');
  if (!Number.isFinite(generatedMs) || !Number.isFinite(nowMs)) {
    return { status: 'unreadable', ageDays: null, ageHours: null };
  }
  const ageMs = nowMs - generatedMs;
  if (ageMs < -HOUR) {
    return { status: 'future', ageDays: null, ageHours: null };
  }
  const ageHours = Math.max(0, ageMs / HOUR);
  if (ageMs > 48 * HOUR) {
    return { status: 'stale', ageDays: Math.floor(ageMs / DAY), ageHours };
  }
  return { status: 'fresh', ageDays: Math.floor(Math.max(0, ageMs) / DAY), ageHours };
}

export function stalenessMessage(result) {
  switch (result.status) {
    case 'stale':
      return `數據係 ${result.ageDays} 日前嘅；所有「今日」、逾期同預測都以舊快照為準。請檢查收集及部署。`;
    case 'unreadable':
      return '數據時間戳缺失或無法讀取；無法確認 dashboard 是否最新。';
    case 'future':
      return '數據時間戳比瀏覽器時間更遲；請檢查 collector 或電腦時鐘。';
    default:
      return '';
  }
}
