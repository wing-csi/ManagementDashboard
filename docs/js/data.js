import { DEMO_DATA } from '../data/demo-data.js';

export const state = { data: null, demo: false, windowDays: 90, repo: 'all', branch: 'all', chart: null, sort: { key: 'date', dir: -1 } };
export const $ = (id) => document.getElementById(id);
export const pct = (num, den, dp = 1) => (den > 0 ? ((num / den) * 100).toFixed(dp) : null);
export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/* ---------------- data loading ---------------- */
export class LoadError extends Error {
  constructor(status) {
    super(`metrics fetch failed: ${status}`);
    this.name = 'LoadError';
    this.status = status;
  }
}

export async function loadData() {
  if (new URLSearchParams(location.search).get('demo') === '1') {
    return { data: DEMO_DATA, demo: true };
  }
  const res = await fetch('./data/metrics.json', { cache: 'no-store' });
  if (!res.ok) throw new LoadError(res.status);
  return { data: await res.json(), demo: false };
}

/* ---------------- task windows ---------------- */
export const toDate = (s) => new Date(s + 'T00:00:00Z');
export const refDate = () => toDate(state.data.generated_at.slice(0, 10));

export function tasksBetween(fromMs, toMs) {
  return state.data.tasks.filter((t) => {
    if (state.repo !== 'all' && t.repo !== state.repo) return false;
    if (state.branch !== 'all' && t.branch !== state.branch) return false;
    const ms = toDate(t.date).getTime();
    return ms >= fromMs && ms < toMs;
  });
}
export function windowTasks() {
  const end = refDate().getTime() + 864e5;
  return tasksBetween(end - state.windowDays * 864e5, end);
}
export function precedingTasks() {
  const end = refDate().getTime() + 864e5 - state.windowDays * 864e5;
  return tasksBetween(end - state.windowDays * 864e5, end);
}
