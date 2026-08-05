import { DEMO_DATA } from '../data/demo-data.js';
import { personOf } from './people.js';

export const state = {
  data: null, demo: false, windowDays: 90,
  repo: 'all', branch: 'all', person: 'all', personIndex: new Map(),
  chart: null, sort: { key: 'date', dir: -1 },
  // 最近 Tasks 表格自己嘅 view state:search、level 同 status 篩,page 係 1-based,
  // 任何收窄結果嘅動作都要 reset 返 1,唔係會停喺一個空頁。
  search: '', level: 'all', taskStatus: 'all', page: 1,
};
export const $ = (id) => document.getElementById(id);
export const pct = (num, den, dp = 1) => (den > 0 ? ((num / den) * 100).toFixed(dp) : null);
export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** 登記冊(plan / defect)喺 GitHub 上面條 link。
 *
 *  `reg.ref` 係 config `registers_ref` 指嗰條 branch — 兩份登記冊可以住喺一條
 *  `docs/*` branch,唔使 merge 入 default branch。冇設就用 HEAD(= default
 *  branch)。寫死 HEAD 嘅話,branch 上面嘅登記冊會照樣出行,但撳落去係 404。
 */
export const registerUrl = (repo, reg) =>
  `https://github.com/${repo}/blob/${reg.ref || 'HEAD'}/${reg.path}`;

/* ---------------- repo scope ----------------
 * state.repo 可以係 'all'、一個 repo 名,或者 'owner:<Person>'。每個 consumer
 * 都要問呢個 predicate,唔好直接比較 state.repo — 咁先唔會有某個 call site
 * 靜靜哋漏咗 owner 呢種寫法。
 */
export const OWNER_PREFIX = 'owner:';
export function repoInScope(repo) {
  if (state.repo === 'all') return true;
  if (state.repo.startsWith(OWNER_PREFIX)) {
    const person = state.repo.slice(OWNER_PREFIX.length);
    return ((state.data.repo_meta || {})[repo] || {}).owner === person;
  }
  return repo === state.repo;
}
/** 揀咗嘅 repo 名;跨越多過一個 repo 嘅時候回 null。 */
export function singleRepo() {
  if (state.repo === 'all' || state.repo.startsWith(OWNER_PREFIX)) return null;
  return state.repo;
}

/** 呢個 task 係咪屬於揀咗嘅人('all' 嘅時候永遠 true)。 */
export function personInScope(task) {
  if (state.person === 'all') return true;
  return personOf(task.author, state.personIndex) === state.person;
}

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

export function tasksBetween(fromMs, toMs, { allPeople = false } = {}) {
  return state.data.tasks.filter((t) => {
    if (!repoInScope(t.repo)) return false;
    if (!allPeople && !personInScope(t)) return false;
    if (state.branch !== 'all' && t.branch !== state.branch) return false;
    const ms = toDate(t.date).getTime();
    return ms >= fromMs && ms < toMs;
  });
}
export function windowTasks(opts) {
  const end = refDate().getTime() + 864e5;
  return tasksBetween(end - state.windowDays * 864e5, end, opts);
}
export function precedingTasks() {
  const end = refDate().getTime() + 864e5 - state.windowDays * 864e5;
  return tasksBetween(end - state.windowDays * 864e5, end);
}
