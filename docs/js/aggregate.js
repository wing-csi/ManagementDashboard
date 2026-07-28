import { state, toDate, refDate, repoInScope } from './data.js';

export const LEVELS = ['L1', 'L2', 'L3', 'L4', 'L5'];
export const AI_LOC_LEVELS = new Set(['L2', 'L3', 'L4', 'L5']);
export const META = {
  L1: { name: '輔助', color: '#CBD2D9', dark: false },
  L2: { name: '部分自動', color: '#9FB6D1', dark: false },
  L3: { name: '有條件自動', color: '#5F8CC6', dark: true },
  L4: { name: '高度自動', color: '#2E5EB8', dark: true },
  L5: { name: '完全自動', color: '#0A2F9C', dark: true },
};
export const UNTAGGED_COLOR = '#DFE1D8';
export const INK = '#191D1B';
export const TABLE_CAP = 80;
export const DEFECT_CAP = 10;
export const FIX_RE = /^(fix|hotfix|revert)\b/i;
export const FAIL_RE = /^(revert|hotfix)\b/i;
export const VIOLATION_META = {
  'direct-push-main': { label: '直接 push 到受監察 branch(冇 PR)', red: true },
  'forbidden-files': { label: 'commit 咗 .env / node_modules / __pycache__', red: true },
  'workflow-deleted': { label: '刪除咗 GitHub Actions workflow', red: true },
  'cross-branch-merge': { label: '跨 feature branch 合併', red: true },
  'core-without-double-review': { label: '核心模組改動欠二次複核', red: true },
  'merged-without-review': { label: '未經任何 review 就 merge', red: false },
  'oversized-pr': { label: '超大 PR(欠分階段提交)', red: false },
};
export const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
export const fmtHours = (h) => h == null ? '–' : (h >= 48 ? (h / 24).toFixed(1) + '<span class="unit">日</span>' : h.toFixed(1) + '<span class="unit">小時</span>');

/* ---------------- aggregation ---------------- */
export function statsFromTasks(list) {
  const s = {
    byLevel: Object.fromEntries(LEVELS.map((l) => [l, 0])),
    untagged: 0, insTotal: 0, insAi: 0, suspects: 0,
    fixTasks: 0, prTotal: 0, reviewedPRs: 0, reworkPRs: 0,
    reworkRounds: [], reworkTurnarounds: [], fixByLevel: {},
    failTasks: 0, meaningful: 0, ciPass: 0, ciTotal: 0, leads: [], fixLeads: [],
    violationCounts: {},
    methods: {},
  };
  for (const t of list) {
    s.insTotal += t.additions || 0;
    const isFix = FIX_RE.test(t.title || '');
    if (isFix) s.fixTasks++;
    if (FAIL_RE.test(t.title || '')) s.failTasks++;
    for (const v of (t.violations || [])) s.violationCounts[v] = (s.violationCounts[v] || 0) + 1;
    if ((t.additions || 0) >= 10) s.meaningful++;
    if (t.kind === 'pr') {
      s.prTotal++;
      // 打回率 分母係「有人 review 過」嘅 PR — 冇人 review 過嘅 PR 根本冇得被打回,
      // 擺入分母只會令個率虛低。
      if (t.reviewed) s.reviewedPRs++;
      if ((t.rework || 0) > 0) {
        s.reworkPRs++;
        s.reworkRounds.push(t.rework);
        if (t.rework_hours != null) s.reworkTurnarounds.push(t.rework_hours);
      }
      if (t.ci) { s.ciTotal++; if (t.ci === 'pass') s.ciPass++; }
      if (t.lead_hours != null) { s.leads.push(t.lead_hours); if (isFix) s.fixLeads.push(t.lead_hours); }
    }
    if (t.level && isFix) s.fixByLevel[t.level] = (s.fixByLevel[t.level] || 0) + 1;
    if (t.level) {
      s.byLevel[t.level]++;
      if (t.method) {
        const mk = t.method.split(':')[0];
        s.methods[mk] = (s.methods[mk] || 0) + 1;
      }
      if (t.check && t.check.indexOf('suspect') === 0) s.suspects++;
      if (AI_LOC_LEVELS.has(t.level)) s.insAi += t.additions || 0;
    } else {
      s.untagged++;
    }
  }
  s.tagged = LEVELS.reduce((a, l) => a + s.byLevel[l], 0);
  s.total = s.tagged + s.untagged;
  s.l3plus = s.byLevel.L3 + s.byLevel.L4 + s.byLevel.L5;
  return s;
}

function weekStartOf(dateStr) {
  const d = toDate(dateStr);
  const back = (d.getUTCDay() + 6) % 7;
  return new Date(d.getTime() - back * 864e5).toISOString().slice(0, 10);
}
export function buildWeekly(list) {
  const map = new Map();
  for (const t of list) {
    const ws = weekStartOf(t.date);
    let row = map.get(ws);
    if (!row) {
      row = { week_start: ws, by_level: Object.fromEntries(LEVELS.map((l) => [l, 0])), untagged: 0, insertions_total: 0, insertions_ai: 0 };
      map.set(ws, row);
    }
    row.insertions_total += t.additions || 0;
    if (t.level) {
      row.by_level[t.level]++;
      if (AI_LOC_LEVELS.has(t.level)) row.insertions_ai += t.additions || 0;
    } else {
      row.untagged++;
    }
  }
  return [...map.values()].sort((a, b) => (a.week_start < b.week_start ? -1 : 1));
}
export const weekL3pct = (w) => {
  const tagged = LEVELS.reduce((a, l) => a + (w.by_level[l] || 0), 0);
  return tagged > 0 ? ((w.by_level.L3 + w.by_level.L4 + w.by_level.L5) / tagged) * 100 : null;
};
export function fillGaps(weeks) {
  if (weeks.length < 2) return weeks.slice();
  const out = [];
  const blank = () => ({ by_level: Object.fromEntries(LEVELS.map((l) => [l, 0])), untagged: 0, insertions_total: 0, insertions_ai: 0 });
  let cursor = toDate(weeks[0].week_start).getTime();
  const last = toDate(weeks[weeks.length - 1].week_start).getTime();
  const byKey = Object.fromEntries(weeks.map((w) => [w.week_start, w]));
  while (cursor <= last) {
    const key = new Date(cursor).toISOString().slice(0, 10);
    out.push(byKey[key] || { week_start: key, ...blank() });
    cursor += 7 * 864e5;
  }
  return out;
}

export function metaInWindow() {
  const rm = state.data.repo_meta || {};
  const end = refDate().getTime() + 864e5;
  const from = end - state.windowDays * 864e5;
  const inWin = (d) => { const ms = toDate(d).getTime(); return ms >= from && ms < end; };
  const out = { deployments: 0, releases: 0, tags: 0, closedUnmerged: 0, quality: {} };
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    out.deployments += (m.deployments || []).filter(inWin).length;
    out.releases += (m.releases || []).filter(inWin).length;
    out.tags += (m.tags || []).filter(inWin).length;
    out.closedUnmerged += (m.closed_unmerged || []).filter(inWin).length;
    if (m.quality) out.quality[repo] = m.quality;
  }
  return out;
}

export function issuesInScope() {
  const rm = state.data.repo_meta || {};
  const out = { open: [], openTotal: 0, closedTotal: 0, milestones: [], hasData: false };
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const iss = m.issues;
    if (!iss) continue;
    out.hasData = true;
    out.openTotal += iss.open_total || 0;
    out.closedTotal += iss.closed_total || 0;
    for (const i of iss.open || []) out.open.push({ ...i, repo });
    for (const ms of iss.milestones || []) out.milestones.push({ ...ms, repo });
  }
  return out;
}
