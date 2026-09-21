import { t } from './i18n/index.js';

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
  stale: (result) => t('misc.staleMessage', { days: result.ageDays }),
  unreadable: () => t('misc.unreadableMessage'),
  future: () => t('misc.futureMessage'),
};

export function stalenessMessage(result) {
  const build = MESSAGE[result.status];
  return build ? build(result) : '';
}
