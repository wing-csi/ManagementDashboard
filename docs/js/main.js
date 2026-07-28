import { state, $, esc, loadData, windowTasks, precedingTasks, LoadError, repoInScope, singleRepo } from './data.js';
import { buildPersonIndex, personOptions } from './people.js';
import { statsFromTasks, buildWeekly, metaInWindow } from './aggregate.js';
import {
  renderKPIs, renderSpectrum, renderChart, renderAlerts, renderDora,
  renderRag, renderQuality, setScopeNotes,
} from './render-kpi.js';
import { renderProjects } from './render-project.js';
import { renderOverview, renderDefects, renderTable } from './render-table.js';

/** eyebrow 要講明而家係邊個嘅視角,否則 filtered dashboard 會被當成全隊數字。 */
export function renderEyebrow() {
  const repos = state.data.repos || [];
  const base = (repos.length === 1 ? repos[0].toUpperCase() : `${repos.length} REPOS`) + ' · GITHUB TELEMETRY';
  $('eyebrow').textContent = state.person === 'all' ? base : `${base} · 負責人 ${state.person}`;
}

export function render() {
  setScopeNotes(state.person !== 'all');
  renderEyebrow();
  const wt = windowTasks();
  const cur = statsFromTasks(wt);
  const prev = statsFromTasks(precedingTasks());
  const weeklyRows = buildWeekly(wt);
  renderKPIs(cur, prev);
  renderSpectrum(cur);
  renderChart(weeklyRows);
  renderAlerts(weeklyRows, cur, prev);
  renderDora(cur, metaInWindow());
  renderRag();
  renderQuality(cur);
  renderProjects();
  renderOverview(cur);
  renderDefects();
  renderTable();
}

(async function init() {
  let data, demo;
  try {
    ({ data, demo } = await loadData());
  } catch (e) {
    const box = $('loadError');
    box.hidden = false;
    $('loadErrorDetail').textContent =
      e instanceof LoadError && e.status === 401
        ? '需要登入。'
        : `(${e instanceof LoadError ? e.status : 'network'})`;
    return;
  }
  state.data = data;
  state.demo = demo;
  state.personIndex = buildPersonIndex(data.people);
  $('demoBadge').classList.toggle('on', demo);

  const repos = data.repos || [];
  renderEyebrow();
  // 負責人 = repo 層面嘅 scoping,所以擺喺 repo select 入面,唔開第四個掣
  const rm = data.repo_meta || {};
  const ownerCounts = new Map();
  for (const r of repos) {
    const owner = (rm[r] || {}).owner;
    if (owner) ownerCounts.set(owner, (ownerCounts.get(owner) || 0) + 1);
  }
  const ownerGroup = ownerCounts.size
    ? `<optgroup label="按負責人">` + [...ownerCounts.entries()]
        .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
        .map(([o, n]) => `<option value="owner:${esc(o)}">${esc(o)} 的項目 (${n})</option>`).join('')
      + `</optgroup>`
    : '';
  const repoOptions = repos.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  const repoGroup = ownerCounts.size
    ? `<optgroup label="個別 repo">${repoOptions}</optgroup>` : repoOptions;
  $('repoSel').innerHTML = `<option value="all">全部 repos</option>` + ownerGroup + repoGroup;

  const ts = data.generated_at.replace('T', ' ').slice(0, 16) + ' UTC';
  $('stamp').textContent = ts;
  $('footStamp').textContent = 'generated ' + ts;

  const rebuildBranches = () => {
    const sel = $('branchSel');
    const only = singleRepo();
    if (!only) {
      // branch 名喺唔同 repo 之間冇比較意義 — 唔係單一 repo 就鎖死
      state.branch = 'all';
      sel.innerHTML = `<option value="all">全部 branches</option>`;
      sel.disabled = true;
      sel.title = '揀咗單一 repo 先可以 filter branch';
      return;
    }
    sel.disabled = false;
    sel.title = '';
    const set = new Set();
    for (const t of state.data.tasks || []) {
      if (t.repo === only && t.branch) set.add(t.branch);
    }
    const branches = [...set].sort();
    if (state.branch !== 'all' && !set.has(state.branch)) state.branch = 'all';
    sel.innerHTML = `<option value="all">全部 branches</option>` +
      branches.map((b) => `<option value="${esc(b)}"${b === state.branch ? ' selected' : ''}>${esc(b)}</option>`).join('');
  };

  const syncOwnerParam = () => {
    const url = new URL(location.href);
    if (state.person === 'all') url.searchParams.delete('owner');
    else url.searchParams.set('owner', state.person);
    history.replaceState(null, '', url);
  };

  // 人係跨 repo 可比較嘅(同 branch 唔同),所以全部 repos 時一樣開住
  const rebuildPeople = () => {
    const inScope = (t) => repoInScope(t.repo) && (state.branch === 'all' || t.branch === state.branch);
    const opts = personOptions(state.data.tasks || [], state.personIndex, inScope);
    if (state.person !== 'all' && !opts.some((o) => o.person === state.person)) {
      state.person = 'all';
    }
    $('personSel').innerHTML = `<option value="all">全部成員</option>` +
      opts.map((o) => `<option value="${esc(o.person)}"${o.person === state.person ? ' selected' : ''}>${esc(o.person)} (${o.count})</option>`).join('');
    syncOwnerParam();
  };

  // ?owner= 係唔可信輸入:淨係攞去同已知名單比對,唔會 render
  const requested = new URLSearchParams(location.search).get('owner');
  if (requested) {
    const known = personOptions(state.data.tasks || [], state.personIndex, () => true);
    if (known.some((o) => o.person === requested)) state.person = requested;
  }

  rebuildBranches();
  rebuildPeople();
  $('repoSel').addEventListener('change', (e) => { state.repo = e.target.value; rebuildBranches(); rebuildPeople(); render(); });
  $('branchSel').addEventListener('change', (e) => { state.branch = e.target.value; rebuildPeople(); render(); });
  $('personSel').addEventListener('change', (e) => { state.person = e.target.value; syncOwnerParam(); render(); });
  $('windowSel').addEventListener('change', (e) => { state.windowDays = +e.target.value; render(); });
  document.querySelectorAll('thead th.sortable').forEach((th) => th.addEventListener('click', () => {
    const k = th.dataset.key;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : -1 };
    renderTable();
  }));
  render();
})();
