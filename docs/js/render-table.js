import { state, $, esc, windowTasks, repoInScope, personInScope, registerUrl } from './data.js';
import { personOf } from './people.js';
import { PAGE_SIZE, DEFECT_CAP, VIOLATION_META } from './aggregate.js?v=zh-20260805-3';

const TYPE_RE = /^(feat|fix|hotfix|revert|refactor|test|docs|chore|build|ci|perf|style)\b/i;
const TYPE_LABEL = {
  feat: '功能', fix: '修復', hotfix: '緊急修復', revert: '回退', refactor: '重構',
  test: '測試', docs: '文件', chore: '雜項', build: '建置', ci: 'CI', perf: '效能',
  style: '格式', other: '其他',
};
export function typeChip(t) {
  const m = TYPE_RE.exec(t || '');
  const key = m?.[1].toLowerCase();
  return key ? `<span class="typechip">${TYPE_LABEL[key] || key}</span>` : '';
}
function fmtBytes(b) {
  return b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : (b / 1024).toFixed(0) + ' KB';
}
function barRow(label, n, max, color, extra) {
  return `<div class="ov-row"><span class="t" title="${esc(label)}">${esc(label)}</span>
    <span class="bar-track"><span class="bar-fill" style="width:${max ? (n / max) * 100 : 0}%;background:${color}"></span></span>
    <span class="n">${extra || n}</span></div>`;
}
const PIE_COLORS = ['#24407E', '#3D67B1', '#2E6B5E', '#6D5A8E', '#B07A1F', '#5F8CC6'];
const UNASSIGNED = '未指定';
const FIXED_UNASSIGNED = '已修 · 未指定';

function sortedCounts(counts) {
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function addPersonCount(counts, name, count) {
  if (!name || !count) return;
  const person = personOf(name, state.personIndex);
  counts.set(person, (counts.get(person) || 0) + count);
}

function isBugIssue(item) {
  return (item.labels || []).some((label) => /^bug$/i.test(label));
}

/** One defect stays one slice even when an Issue has multiple assignees. */
function addFixOwnerCount(counts, names) {
  const people = [...new Set((names || [])
    .map((name) => personOf(name, state.personIndex))
    .filter(Boolean))];
  const label = people.join(' + ') || FIXED_UNASSIGNED;
  counts.set(label, (counts.get(label) || 0) + 1);
}

function pieMarkup(segments, total, centerLabel, centerSub) {
  let offset = 0;
  const circles = segments.map((segment) => {
    const share = total ? segment.count / total * 100 : 0;
    const dashOffset = -offset;
    offset += share;
    const title = `${segment.name}: ${segment.count} / ${total} (${share.toFixed(1)}%)`;
    return `<circle class="pie-slice" data-name="${esc(segment.name)}" cx="95" cy="95" r="68" pathLength="100"
      stroke="${segment.color}" stroke-dasharray="${share} ${100 - share}" stroke-dashoffset="${dashOffset}">
      <title>${esc(title)}</title></circle>`;
  }).join('');
  const legend = segments.map((segment) => {
    const share = total ? segment.count / total * 100 : 0;
    const selected = segment.name === state.person ? ' is-selected' : '';
    return `<div class="pie-legend-row${selected}" data-name="${esc(segment.name)}">
      <span class="pie-swatch" style="background:${segment.color}"></span>
      <span class="pie-name" title="${esc(segment.name)}">${esc(segment.name)}</span>
      <span class="pie-metric">${segment.count} / ${total} · ${share.toFixed(1)}%</span>
    </div>`;
  }).join('');
  const aria = segments.map((segment) => `${segment.name} ${segment.count}`).join(', ');
  return `<div class="pie-layout">
    <svg class="pie-svg" viewBox="0 0 190 190" role="img" aria-label="${esc(`${centerLabel} ${total}; ${aria}`)}">
      <circle class="pie-track" cx="95" cy="95" r="68"></circle>${circles}
      <text class="pie-total" x="95" y="94">${total}</text>
      <text class="pie-total-label" x="95" y="116">${esc(centerSub)}</text>
    </svg>
    <div class="pie-legend">${legend}</div>
  </div>`;
}

function renderRegisterPies(rm) {
  const planCounts = new Map();
  let planTotal = 0;
  for (const [repo, meta] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const plan = meta.plan;
    if (!plan) continue;
    // Task-level markers are the most specific signal. The declared repo owner
    // owns the rest of the plan by default; this also makes pre-assignment
    // payloads useful once owner metadata is present.
    if (!Array.isArray(plan.assignments) && !meta.owner) continue;
    planTotal += plan.total || 0;
    const assignments = Array.isArray(plan.assignments) ? plan.assignments : [];
    const assigned = assignments.reduce((sum, row) => sum + (row.tasks || 0), 0);
    for (const row of assignments) addPersonCount(planCounts, row.name, row.tasks || 0);
    const remaining = plan.unassigned ?? Math.max(0, (plan.total || 0) - assigned);
    if (remaining) addPersonCount(planCounts, meta.owner || UNASSIGNED, remaining);
  }
  if (planTotal) {
    const planSegments = sortedCounts(planCounts).map(([name, count], index) => ({
      name, count, color: name === UNASSIGNED ? '#C7CDC9' : PIE_COLORS[index % PIE_COLORS.length],
    }));
    $('planAssignmentPie').innerHTML = pieMarkup(planSegments, planTotal, '計劃工作', '項工作');
  } else {
    $('planAssignmentPie').innerHTML = '<div class="pie-empty">未有可用分配數據 — 請設定程式庫負責人或工作負責人。</div>';
  }

  const fixerCounts = new Map();
  let defectTotal = 0;
  let openTotal = 0;
  let fixedTotal = 0;
  for (const [repo, meta] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const issues = meta.issues;
    for (const item of (issues?.open || []).filter(isBugIssue)) {
      defectTotal += 1;
      openTotal += 1;
    }
    for (const item of (issues?.closed_recent || []).filter(isBugIssue)) {
      defectTotal += 1;
      fixedTotal += 1;
      addFixOwnerCount(fixerCounts, item.assignees);
    }
    for (const item of (meta.defects?.items || [])) {
      defectTotal += 1;
      if (item.open) {
        openTotal += 1;
      } else {
        fixedTotal += 1;
        addFixOwnerCount(fixerCounts, item.fixed_by ? [item.fixed_by] : []);
      }
    }
    for (const item of (meta.plan?.open_tasks || []).filter((task) => task.bug)) {
      defectTotal += 1;
      openTotal += 1;
    }
  }
  if (defectTotal) {
    const defectSegments = sortedCounts(fixerCounts).map(([name, count], index) => ({
      name, count, color: name === FIXED_UNASSIGNED ? '#C7CDC9' : PIE_COLORS[index % PIE_COLORS.length],
    }));
    if (openTotal) defectSegments.push({ name: '未修', count: openTotal, color: '#C2452D' });
    $('defectFixPie').innerHTML = pieMarkup(defectSegments, defectTotal, '缺陷', `${fixedTotal} 已修`);
  } else {
    $('defectFixPie').innerHTML = '<div class="pie-empty">未有缺陷數據 — 可使用有 bug 標籤的 GitHub Issue、計劃檔 #bug 或缺陷登記冊。</div>';
  }
}

export function renderOverview(cur) {
  const rm = state.data.repo_meta || {};
  // languages(scope 內 repos 加總)
  const lang = {}; let disk = 0;
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    disk += m.disk_kb || 0;
    for (const it of ((m.languages || {}).items || [])) lang[it.name] = (lang[it.name] || 0) + it.bytes;
  }
  const langs = Object.entries(lang).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const lmax = langs.length ? langs[0][1] : 0;
  const RAMP = ['#24407E', '#3D67B1', '#5F8CC6', '#8FA8CB', '#BFCCE0', '#D7DEEA'];
  $('ovLangs').innerHTML = langs.map(([n, b], i) => barRow(n, b, lmax, RAMP[i], fmtBytes(b))).join('')
    || '<div class="ov-sub">無語言數據</div>';
  if (langs.length) $('ovLangs').innerHTML += `<div class="ov-sub">程式庫大小 ${(disk / 1024).toFixed(1)} MB（Git）</div>`;
  // commit types(window)
  const types = {};
  for (const t of windowTasks()) {
    const m = TYPE_RE.exec(t.title || '');
    const k = m ? m[1].toLowerCase().replace(/^(hotfix|revert)$/, 'fix') : 'other';
    types[k] = (types[k] || 0) + 1;
  }
  const te = Object.entries(types).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const tmax = te.length ? te[0][1] : 0;
  $('ovTypes').innerHTML = te.map(([n, c], i) => barRow(TYPE_LABEL[n] || n, c, tmax, RAMP[i])).join('')
    || '<div class="ov-sub">此範圍內無工作</div>';
  // monthly(全部 tasks,唔跟 window)
  const mon = {};
  for (const t of (state.data.tasks || []).filter((t) => repoInScope(t.repo) && personInScope(t) && (state.branch === 'all' || t.branch === state.branch))) {
    const k = t.date.slice(0, 7);
    mon[k] = (mon[k] || 0) + 1;
  }
  const me = Object.entries(mon).sort().slice(-10);
  const mmax = Math.max(...me.map(([, c]) => c), 1);
  $('ovMonthly').innerHTML = me.map(([k, c]) => barRow(k, c, mmax, '#2E6B5E')).join('')
    || '<div class="ov-sub">無數據</div>';
  renderRegisterPies(rm);
  // contributors(window)
  // 貢獻者係比較視角,亦係揀人嘅入口 — 保持全員,只標示揀咗邊個
  const by = {};
  for (const t of windowTasks({ allPeople: true })) {
    if (!t.author) continue;
    const p = personOf(t.author, state.personIndex);
    by[p] = (by[p] || 0) + 1;
  }
  // 唔截頭 N — 貢獻少嘅人一樣要見到,% 加埋先夠 100
  const ce = Object.entries(by).sort((a, b) => b[1] - a[1]);
  const total = ce.reduce((s, [, c]) => s + c, 0);
  const AV = ['#24407E', '#3D67B1', '#5F8CC6', '#2E6B5E', '#B07A1F', '#6D5A8E'];
  $('ovContribs').innerHTML = ce.map(([n, c], i) => `<div class="contrib${n === state.person ? ' is-selected' : ''}">
      <div class="nm"><span class="av" style="background:${AV[i % 6]}">${esc(n[0].toUpperCase())}</span><span title="${esc(n)}">${esc(n)}</span></div>
      <div class="ct">${c}<span style="font-size:var(--fs-xs);color:var(--muted)"> 項工作</span></div>
      <div class="pc">佔此範圍 ${total ? ((c / total) * 100).toFixed(1) : 0}%</div>
    </div>`).join('') || '<div class="ov-sub">此範圍內無工作</div>';
}
export function renderDefects() {
  const rm = state.data.repo_meta || {};
  const sev = (labels) => {
    const L = labels.map((x) => x.toLowerCase());
    if (L.some((x) => /critical|high|p0|p1/.test(x))) return ['高', 'var(--alert)'];
    if (L.some((x) => /medium|p2/.test(x))) return ['中', 'var(--warn)'];
    if (L.some((x) => /low|p[34]/.test(x))) return ['低', '#2E7D4F'];
    return ['—', '#9AA5A0'];
  };
  const rows = [];
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const iss = m.issues;
    if (iss) {
      for (const i of (iss.open || []).filter(isBugIssue))
        rows.push({ ...i, repo, status: 'Open' });
      for (const i of (iss.closed_recent || []).filter(isBugIssue))
        rows.push({ ...i, repo, status: 'Fixed' });
    }
    // plan-file defects: `- [ ] … #bug !P1 due:YYYY-MM-DD` lines in the repo's plan_file.
    // The parser only emits unticked tasks, so these are always Open.
    // per-repo defect register (config: defect_file) — 第三個來源。issues 喺
    // 呢個 org 冇數據,而 plan file 只會出未打勾嘅項目,所以呢度係唯一有
    // 「已修」嗰半嘅來源。
    const dfx = m.defects;
    for (const i of (dfx?.items || []))
      rows.push({
        number: null, title: i.title, repo,
        status: i.open ? 'Open' : 'Fixed',
        url: registerUrl(repo, dfx),
        labels: i.severity ? [i.severity] : [], assignees: i.fixed_by ? [i.fixed_by] : [],
        due: i.fixed || i.found,
      });
    const plan = m.plan;
    for (const t of (plan?.open_tasks || []).filter((t) => t.bug))
      rows.push({
        number: null, title: t.title, repo, status: 'Open',
        url: registerUrl(repo, plan),
        labels: t.priority ? [t.priority] : [], assignees: [t.assignee || m.owner].filter(Boolean), due: t.due,
      });
  }
  rows.sort((a, b) => (a.status === 'Open' ? 0 : 1) - (b.status === 'Open' ? 0 : 1));
  $('defectCount').textContent = rows.length > DEFECT_CAP
    ? `${rows.length} 項,顯示頭 ${DEFECT_CAP}` : `${rows.length} 項`;
  $('defectRows').innerHTML = rows.slice(0, DEFECT_CAP).map((r) => {
    const [sl, sc] = sev(r.labels || []);
    return `<tr>
      <td><a class="tlink" href="${esc(r.url)}" target="_blank" rel="noopener">${r.number ? '#' + r.number : '計劃'}</a></td>
      <td class="repo">${esc(r.repo.split('/').pop())}</td>
      <td><span class="sevdot" style="background:${sc}"></span>${sl}</td>
      <td class="subject" title="${esc(r.title)}">${esc(r.title)}</td>
      <td style="color:${r.status === 'Open' ? 'var(--alert)' : 'var(--muted)'};font-weight:${r.status === 'Open' ? 700 : 400}">${r.status === 'Open' ? '未修' : '已修'}</td>
      <td class="mono" style="font-size:var(--fs-xs)">${esc((r.assignees || []).join(', ') || '–')}</td>
      <td class="mono" style="font-size:var(--fs-xs)">${esc(r.due || r.closed || '–')}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="mono" style="color:var(--muted)">無缺陷 — 可建立有 bug 標籤的 GitHub Issue，或在計劃檔寫入 <code>- [ ] … #bug !P1 due:2026-08-01</code></td></tr>';
}

/** 搜尋比對原始欄位,唔係 render 出嚟嘅 HTML — markup(例如 typechip、⛔ 標記)
 *  永遠唔應該影響搵到啲乜。 */
function matchesFilters(t) {
  if (state.level !== 'all' && (t.level || 'none') !== state.level) return false;
  if (!taskMatchesStatus(t, state.taskStatus)) return false;
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  const prRef = t.kind === 'pr' ? `#${t.id}` : '';
  return [t.title, t.author, t.branch, t.id, prRef]
    .some((v) => (v || '').toLowerCase().includes(q));
}

/** Status is a second, independent task-table dimension. Governance warnings
 * stay separate from true red lines even though both live in `violations`. */
export function taskMatchesStatus(t, status) {
  const violations = t.violations || [];
  switch (status) {
    case 'redline': return violations.some((v) => VIOLATION_META[v]?.red === true);
    case 'warning': return violations.some((v) => VIOLATION_META[v]?.red !== true);
    case 'suspect': return (t.check || '').startsWith('suspect');
    case 'ci-fail': return t.ci === 'fail';
    default: return true;
  }
}

/** Make the parent PR explicit. A direct commit has no parent PR, but its SHA
 * remains available as a secondary link so the row is still traceable. */
export function taskPullRequestMarkup(t) {
  if (t.kind === 'pr') {
    return `<a class="tlink pr-ref" href="${esc(t.url)}" target="_blank" rel="noopener" aria-label="PR #${esc(t.id)}">#${esc(t.id)}</a>`;
  }
  return `<span class="no-pr" title="直接提交 · 無所屬 PR">無 PR</span>`
    + `<a class="commit-ref" href="${esc(t.url)}" target="_blank" rel="noopener" title="提交 ${esc(t.id)}">${esc(t.id)}</a>`;
}

function violationFlags(t) {
  const violations = t.violations || [];
  const title = (list) => esc(list.map((v) => (VIOLATION_META[v] || {}).label || v).join(' · '));
  const red = violations.filter((v) => VIOLATION_META[v]?.red === true);
  const warnings = violations.filter((v) => VIOLATION_META[v]?.red !== true);
  return `${red.length ? `<span class="vflag is-red" title="${title(red)}">⛔</span>` : ''}`
    + `${warnings.length ? `<span class="vflag is-warning" title="${title(warnings)}">!</span>` : ''}`;
}

export function renderTable() {
  const rows = windowTasks().filter(matchesFilters);
  const order = { null: 0, L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 };
  const { key, dir } = state.sort;
  rows.sort((a, b) => {
    const va = key === 'level' ? order[a.level] : a[key];
    const vb = key === 'level' ? order[b.level] : b[key];
    return (va > vb ? 1 : va < vb ? -1 : 0) * dir;
  });

  document.querySelectorAll('thead th.sortable').forEach((th) => {
    th.querySelector('.arrow').textContent = th.dataset.key === key ? (dir === 1 ? '▲' : '▼') : '';
  });

  const shown = rows.slice(0, state.page * PAGE_SIZE);
  $('taskRows').innerHTML = shown.map((r) => `
    <tr>
      <td class="mono">${r.date}</td>
      <td class="repo" title="${esc(r.repo)}">${esc(r.repo.split('/').pop())}</td>
      <td class="mono" style="font-size:var(--fs-xs)" title="${esc(r.author || '')}">${esc(r.author || '–')}</td>
      <td class="pr-cell">${taskPullRequestMarkup(r)}</td>
      <td class="branch" title="${esc(r.branch || '')}">${esc(r.branch || '–')}</td>
      <td class="subject" title="${esc(r.title)}">${typeChip(r.title)}${esc(r.title)}</td>
      <td class="lvlcell">${r.level ? `<span class="chip ${r.level}">${r.level}</span>` : '<span class="chip none">—</span>'}${r.check && r.check.indexOf('suspect') === 0 ? `<span class="flag" title="${esc(r.check)}">⚠</span>` : ''}${violationFlags(r)}</td>
      <td class="lines">+${r.additions}<span class="del">−${r.deletions}</span></td>
    </tr>`).join('') || '<tr><td colspan="8" class="mono" style="color:var(--muted)">此範圍內無工作</td></tr>';
  $('tableCap').textContent = rows.length ? `顯示 ${shown.length} / ${rows.length} 項工作` : '';
  $('tableMore').hidden = shown.length >= rows.length;
}
