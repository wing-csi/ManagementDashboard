import { state, $, esc, windowTasks, repoInScope, personInScope, registerUrl } from './data.js';
import { personOf } from './people.js';
import { PAGE_SIZE, DEFECT_CAP, VIOLATION_META } from './aggregate.js';

const TYPE_RE = /^(feat|fix|hotfix|revert|refactor|test|docs|chore|build|ci|perf|style)\b/i;
export function typeChip(t) {
  const m = TYPE_RE.exec(t || '');
  return m ? `<span class="typechip">${m[1].toLowerCase()}</span>` : '';
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

function sortedCounts(counts) {
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function addPersonCount(counts, name, count) {
  if (!name || !count) return;
  const person = personOf(name, state.personIndex);
  counts.set(person, (counts.get(person) || 0) + count);
}

function pieMarkup(segments, total, centerLabel, centerSub) {
  let offset = 0;
  const circles = segments.map((segment) => {
    const share = total ? segment.count / total * 100 : 0;
    const dashOffset = -offset;
    offset += share;
    const title = `${segment.name}: ${segment.count} / ${total} (${share.toFixed(1)}%)`;
    return `<circle class="pie-slice" data-name="${esc(segment.name)}" cx="50" cy="50" r="36" pathLength="100"
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
    <svg class="pie-svg" viewBox="0 0 100 100" role="img" aria-label="${esc(`${centerLabel} ${total}; ${aria}`)}">
      <circle class="pie-track" cx="50" cy="50" r="36"></circle>${circles}
      <text class="pie-total" x="50" y="40">${total}</text>
      <text class="pie-total-label" x="50" y="66">${esc(centerSub)}</text>
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
    // Old metrics payloads have no assignments key. Do not misreport those
    // plans as 100% unassigned; the next collector run makes this measurable.
    if (!plan || !Array.isArray(plan.assignments)) continue;
    planTotal += plan.total || 0;
    for (const row of plan.assignments) addPersonCount(planCounts, row.name, row.tasks || 0);
    if (plan.unassigned) planCounts.set('未指定', (planCounts.get('未指定') || 0) + plan.unassigned);
  }
  if (planTotal) {
    const planSegments = sortedCounts(planCounts).map(([name, count], index) => ({
      name, count, color: name === '未指定' ? '#C7CDC9' : PIE_COLORS[index % PIE_COLORS.length],
    }));
    $('planAssignmentPie').innerHTML = pieMarkup(planSegments, planTotal, 'Plan tasks', 'plan tasks');
  } else {
    $('planAssignmentPie').innerHTML = '<div class="pie-empty">未有可用分配數據 — 喺 plan task 加 <code>assignee:Name</code>,再重新收集。</div>';
  }

  const fixerCounts = new Map();
  let defectTotal = 0;
  let openTotal = 0;
  let fixedTotal = 0;
  for (const [repo, meta] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    for (const item of (meta.defects?.items || [])) {
      defectTotal += 1;
      if (item.open) {
        openTotal += 1;
      } else {
        fixedTotal += 1;
        addPersonCount(fixerCounts, item.fixed_by || '已修 · 未指定', 1);
      }
    }
  }
  if (defectTotal) {
    const defectSegments = sortedCounts(fixerCounts).map(([name, count], index) => ({
      name, count, color: name === '已修 · 未指定' ? '#C7CDC9' : PIE_COLORS[index % PIE_COLORS.length],
    }));
    if (openTotal) defectSegments.push({ name: '未修', count: openTotal, color: '#C2452D' });
    $('defectFixPie').innerHTML = pieMarkup(defectSegments, defectTotal, 'Defects', `${fixedTotal} fixed`);
  } else {
    $('defectFixPie').innerHTML = '<div class="pie-empty">未有 defect 登記冊數據 — 已修項目可加 <code>fixed-by:Name</code>。</div>';
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
  if (langs.length) $('ovLangs').innerHTML += `<div class="ov-sub">repo size ${(disk / 1024).toFixed(1)} MB(git)</div>`;
  // commit types(window)
  const types = {};
  for (const t of windowTasks()) {
    const m = TYPE_RE.exec(t.title || '');
    const k = m ? m[1].toLowerCase().replace(/^(hotfix|revert)$/, 'fix') : 'other';
    types[k] = (types[k] || 0) + 1;
  }
  const te = Object.entries(types).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const tmax = te.length ? te[0][1] : 0;
  $('ovTypes').innerHTML = te.map(([n, c], i) => barRow(n, c, tmax, RAMP[i])).join('')
    || '<div class="ov-sub">此範圍內無 tasks</div>';
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
      <div class="ct">${c}<span style="font-size:var(--fs-xs);color:var(--muted)"> tasks</span></div>
      <div class="pc">${total ? ((c / total) * 100).toFixed(1) : 0}% of window</div>
    </div>`).join('') || '<div class="ov-sub">此範圍內無 tasks</div>';
}
export function renderDefects() {
  const rm = state.data.repo_meta || {};
  const sev = (labels) => {
    const L = labels.map((x) => x.toLowerCase());
    if (L.some((x) => /critical|high|p0|p1/.test(x))) return ['High', 'var(--alert)'];
    if (L.some((x) => /medium|p2/.test(x))) return ['Medium', 'var(--warn)'];
    if (L.some((x) => /low|p[34]/.test(x))) return ['Low', '#2E7D4F'];
    return ['—', '#9AA5A0'];
  };
  const rows = [];
  for (const [repo, m] of Object.entries(rm)) {
    if (!repoInScope(repo)) continue;
    const iss = m.issues;
    if (iss) {
      for (const i of (iss.open || []).filter((i) => i.labels.some((l) => /^bug$/i.test(l))))
        rows.push({ ...i, repo, status: 'Open' });
      for (const i of (iss.closed_recent || []).filter((i) => i.labels.some((l) => /^bug$/i.test(l))))
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
        labels: t.priority ? [t.priority] : [], assignees: t.assignee ? [t.assignee] : [], due: t.due,
      });
  }
  rows.sort((a, b) => (a.status === 'Open' ? 0 : 1) - (b.status === 'Open' ? 0 : 1));
  $('defectCount').textContent = rows.length > DEFECT_CAP
    ? `${rows.length} 項,顯示頭 ${DEFECT_CAP}` : `${rows.length} 項`;
  $('defectRows').innerHTML = rows.slice(0, DEFECT_CAP).map((r) => {
    const [sl, sc] = sev(r.labels || []);
    return `<tr>
      <td><a class="tlink" href="${esc(r.url)}" target="_blank" rel="noopener">${r.number ? '#' + r.number : 'plan'}</a></td>
      <td class="repo">${esc(r.repo.split('/').pop())}</td>
      <td><span class="sevdot" style="background:${sc}"></span>${sl}</td>
      <td class="subject" title="${esc(r.title)}">${esc(r.title)}</td>
      <td style="color:${r.status === 'Open' ? 'var(--alert)' : 'var(--muted)'};font-weight:${r.status === 'Open' ? 700 : 400}">${r.status === 'Open' ? '未修' : 'Fixed'}</td>
      <td class="mono" style="font-size:var(--fs-xs)">${esc((r.assignees || []).join(', ') || '–')}</td>
      <td class="mono" style="font-size:var(--fs-xs)">${esc(r.due || r.closed || '–')}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="mono" style="color:var(--muted)">冇 defect — 開 issue 打 bug label,或者喺 plan file 寫 <code>- [ ] … #bug !P1 due:2026-08-01</code></td></tr>';
}

/** 搜尋比對原始欄位,唔係 render 出嚟嘅 HTML — markup(例如 typechip、⛔ 標記)
 *  永遠唔應該影響搵到啲乜。 */
function matchesFilters(t) {
  if (state.level !== 'all' && (t.level || 'none') !== state.level) return false;
  if (!taskMatchesStatus(t, state.taskStatus)) return false;
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  return [t.title, t.author, t.branch].some((v) => (v || '').toLowerCase().includes(q));
}

/** Status is a second, independent task-table dimension. Governance warnings
 * stay separate from true red lines even though both live in `violations`. */
export function taskMatchesStatus(t, status) {
  const violations = t.violations || [];
  switch (status) {
    case 'redline': return violations.some((v) => VIOLATION_META[v]?.red === true);
    case 'warning': return violations.some((v) => VIOLATION_META[v]?.red !== true);
    case 'suspect': return (t.check || '').startsWith('suspect');
    case 'rework': return (t.rework || 0) > 0;
    case 'ci-fail': return t.ci === 'fail';
    default: return true;
  }
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
      <td><a class="tlink" href="${esc(r.url)}" target="_blank" rel="noopener">${r.kind === 'pr' ? '#' + esc(r.id) : esc(r.id)}</a>${(r.rework || 0) > 0 ? `<span class="rework" title="被打回 ${r.rework} 輪">↩${r.rework}</span>` : ''}</td>
      <td class="branch" title="${esc(r.branch || '')}">${esc(r.branch || '–')}</td>
      <td class="subject" title="${esc(r.title)}">${typeChip(r.title)}${esc(r.title)}</td>
      <td class="lvlcell">${r.level ? `<span class="chip ${r.level}">${r.level}</span>` : '<span class="chip none">—</span>'}${r.check && r.check.indexOf('suspect') === 0 ? `<span class="flag" title="${esc(r.check)}">⚠</span>` : ''}${violationFlags(r)}</td>
      <td class="lines">+${r.additions}<span class="del">−${r.deletions}</span></td>
    </tr>`).join('') || '<tr><td colspan="8" class="mono" style="color:var(--muted)">此範圍內無 tasks</td></tr>';
  $('tableCap').textContent = rows.length ? `顯示 ${shown.length} / ${rows.length} 個 tasks` : '';
  $('tableMore').hidden = shown.length >= rows.length;
}
